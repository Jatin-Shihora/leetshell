"""Extract LeetCode cookies from browsers.

Tries two approaches in order:
1. Read cookies directly from the browser's cookie database on disk
   (works when browser is already running and user is logged in).
2. Launch a browser with Chrome DevTools Protocol and wait for login.

Works with Edge, Chrome, Brave, and Arc on Windows.
"""

import asyncio
import base64
import ctypes
import ctypes.wintypes
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from dataclasses import dataclass

import httpx
import websockets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass
class BrowserCookies:
    leetcode_session: str = ""
    csrftoken: str = ""

    @property
    def is_complete(self) -> bool:
        return bool(self.leetcode_session and self.csrftoken)


class CookieExtractionError(Exception):
    pass


class BrowserNotFoundError(CookieExtractionError):
    pass


class BrowserAlreadyRunningError(CookieExtractionError):
    pass


# ── Browser discovery ──────────────────────────────────────────────────────

def _build_browser_list() -> list[tuple[str, list[str], str]]:
    """Returns [(display_name, [hardcoded_paths], exe_name_for_which)]."""
    local = os.environ.get("LOCALAPPDATA", "")
    pf = os.environ.get("PROGRAMFILES", "")
    pf86 = os.environ.get("PROGRAMFILES(X86)", "")
    win_apps = os.path.join(local, "Microsoft", "WindowsApps")

    return [
        ("Microsoft Edge", [
            os.path.join(pf86, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(pf, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(win_apps, "msedge.exe"),
        ], "msedge"),
        ("Google Chrome", [
            os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(pf86, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"),
        ], "chrome"),
        ("Arc", [
            os.path.join(win_apps, "Arc.exe"),
            os.path.join(local, "Arc", "Application", "arc.exe"),
            os.path.join(pf, "Arc", "Application", "arc.exe"),
            os.path.join(local, "Programs", "Arc", "Arc.exe"),
        ], "Arc"),
        ("Brave", [
            os.path.join(pf, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            os.path.join(pf86, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            os.path.join(local, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
        ], "brave"),
    ]


def _get_browser_profile_dir(browser_name: str) -> str | None:
    """Return the User Data directory for a Chromium browser, or None."""
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = {
        "Microsoft Edge": [
            os.path.join(local, "Microsoft", "Edge", "User Data"),
        ],
        "Google Chrome": [
            os.path.join(local, "Google", "Chrome", "User Data"),
        ],
        "Arc": [
            os.path.join(local, "Arc", "User Data"),
            # MSIX installs - search Packages dir
        ],
        "Brave": [
            os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data"),
        ],
    }

    for path in candidates.get(browser_name, []):
        if os.path.isdir(path):
            return path

    # Arc MSIX: look in Packages folder
    if browser_name == "Arc":
        packages = os.path.join(local, "Packages")
        if os.path.isdir(packages):
            for d in os.listdir(packages):
                if "Arc" in d or "TheBrowserCompany" in d:
                    arc_data = os.path.join(
                        packages, d, "LocalCache", "Local", "Arc", "User Data"
                    )
                    if os.path.isdir(arc_data):
                        return arc_data

    return None


def find_browser_exe(browser_name: str) -> str | None:
    """Find the executable path for a browser by name. Returns None if not installed."""
    browsers = _build_browser_list()
    for name, paths, exe_name in browsers:
        if name == browser_name:
            for path in paths:
                if os.path.isfile(path):
                    return path
            found = shutil.which(exe_name)
            if found:
                return found
            return None
    return None


def get_all_browser_names() -> list[str]:
    """Return all supported browser names in display order."""
    return [name for name, _, _ in _build_browser_list()]


def get_fallback_browser(skip: str | set[str] = "") -> str | None:
    """Return the next available browser to try, skipping ones already tried."""
    if isinstance(skip, str):
        skip = {skip}
    for name in get_all_browser_names():
        if name in skip:
            continue
        if find_browser_exe(name):
            return name
    return None


def try_read_cookies_from_any_browser() -> tuple[BrowserCookies | None, str | None]:
    """Try reading LeetCode cookies from ANY installed browser's disk DB.

    Returns (cookies, browser_name) if found, (None, None) otherwise.
    """
    for name in get_all_browser_names():
        cookies = try_read_cookies_from_disk(name)
        if cookies and cookies.is_complete:
            return cookies, name
    return None, None


# ── Disk-based cookie reading (encrypted Chromium cookies) ─────────────────

class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _dpapi_decrypt(encrypted: bytes) -> bytes:
    """Decrypt data using Windows DPAPI (CryptUnprotectData)."""
    blob_in = _DATA_BLOB(
        len(encrypted),
        ctypes.create_string_buffer(encrypted, len(encrypted)),
    )
    blob_out = _DATA_BLOB()

    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    )
    if not ok:
        raise CookieExtractionError("DPAPI decryption failed")

    data = ctypes.string_at(blob_out.pbData, blob_out.cbData)
    ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    return data


def _get_chromium_key(user_data_dir: str) -> bytes:
    """Read and decrypt the AES key from Chromium's Local State file."""
    local_state_path = os.path.join(user_data_dir, "Local State")
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)

    b64_key = local_state["os_crypt"]["encrypted_key"]
    encrypted_key = base64.b64decode(b64_key)

    # Strip the "DPAPI" prefix (5 bytes) then decrypt with DPAPI
    return _dpapi_decrypt(encrypted_key[5:])


def _decrypt_cookie_value(encrypted_value: bytes, key: bytes) -> str:
    """Decrypt a Chromium cookie value."""
    if encrypted_value[:3] == b"v10" or encrypted_value[:3] == b"v20":
        # AES-256-GCM: nonce (12 bytes) + ciphertext
        nonce = encrypted_value[3:15]
        ciphertext = encrypted_value[15:]
        aes = AESGCM(key)
        return aes.decrypt(nonce, ciphertext, None).decode("utf-8")

    # Older format: raw DPAPI
    return _dpapi_decrypt(encrypted_value).decode("utf-8")


def _find_cookie_db(user_data_dir: str) -> str | None:
    """Find the Cookies database file within a Chromium profile."""
    # Modern Chromium: Default/Network/Cookies
    # Older Chromium: Default/Cookies
    # Also check Profile 1, Profile 2, etc.
    for profile in ["Default", "Profile 1", "Profile 2", "Profile 3"]:
        for subpath in [
            os.path.join(profile, "Network", "Cookies"),
            os.path.join(profile, "Cookies"),
        ]:
            full = os.path.join(user_data_dir, subpath)
            if os.path.isfile(full):
                return full
    return None


def _read_cookies_from_db(db_path: str, key: bytes) -> BrowserCookies:
    """Read and decrypt LeetCode cookies from a Chromium cookie database."""
    cookies = BrowserCookies()

    conn = sqlite3.connect(
        f"file:{db_path}?mode=ro&immutable=1",
        uri=True,
        timeout=3,
    )
    try:
        cursor = conn.execute(
            "SELECT name, encrypted_value FROM cookies "
            "WHERE host_key LIKE '%leetcode.com' "
            "AND name IN ('LEETCODE_SESSION', 'csrftoken')"
        )
        for name, encrypted_value in cursor:
            if not encrypted_value:
                continue
            try:
                value = _decrypt_cookie_value(encrypted_value, key)
            except Exception:
                continue
            if name == "LEETCODE_SESSION":
                cookies.leetcode_session = value
            elif name == "csrftoken":
                cookies.csrftoken = value
    finally:
        conn.close()

    return cookies


def try_read_cookies_from_disk(browser_name: str) -> BrowserCookies | None:
    """Try to read LeetCode cookies from the browser's cookie database.

    Returns BrowserCookies if both cookies are found, None otherwise.
    This works even when the browser is running - it opens the DB read-only.
    """
    profile_dir = _get_browser_profile_dir(browser_name)
    if not profile_dir:
        return None

    db_path = _find_cookie_db(profile_dir)
    if not db_path:
        return None

    try:
        key = _get_chromium_key(profile_dir)
    except Exception:
        return None

    # Method 1: open directly with immutable flag (no locks acquired)
    try:
        cookies = _read_cookies_from_db(db_path, key)
        if cookies.is_complete:
            return cookies
    except Exception:
        pass

    # Method 2: copy to temp file then read
    try:
        tmp = tempfile.mktemp(suffix=".db")
        shutil.copy2(db_path, tmp)
        try:
            cookies = _read_cookies_from_db(tmp, key)
            if cookies.is_complete:
                return cookies
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass
    except Exception:
        pass

    return None


# ── Top-level extraction (disk first, then CDP) ───────────────────────────

async def extract_cookies(
    browser_name: str,
    on_status: callable = None,
) -> BrowserCookies:
    """Extract LeetCode cookies - tries disk read first, then CDP.

    This is the main entry point. It will:
    1. Try reading cookies from the browser's local cookie DB (instant, no browser launch needed).
    2. If that fails, launch the browser with CDP and wait for the user to log in.
    """
    # Step 1: Try reading from disk (works if already logged in)
    if on_status:
        on_status("Checking for existing session...")

    cookies = try_read_cookies_from_disk(browser_name)
    if cookies and cookies.is_complete:
        return cookies

    # Step 2: Fall back to CDP
    exe = find_browser_exe(browser_name)
    if not exe:
        raise BrowserNotFoundError(f"Could not find {browser_name}")

    return await extract_cookies_via_cdp(exe, on_status)


# ── CDP-based cookie extraction ───────────────────────────────────────────

CDP_PORT = 9222


async def extract_cookies_via_cdp(
    browser_exe: str,
    on_status: callable = None,
) -> BrowserCookies:
    """Launch browser with CDP, wait for user to log in, extract cookies."""
    tmp_profile = tempfile.mkdtemp(prefix="leetcode_login_")

    # Find an available port
    port = CDP_PORT
    for _ in range(10):
        try:
            async with httpx.AsyncClient() as client:
                await client.get(f"http://127.0.0.1:{port}/json/version", timeout=0.5)
            port += 1
        except Exception:
            break

    proc = subprocess.Popen(
        [
            browser_exe,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={tmp_profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "https://leetcode.com/accounts/login/",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if on_status:
        on_status("Waiting for browser to start...")

    cdp_url = f"http://127.0.0.1:{port}"
    async with httpx.AsyncClient() as client:
        for _ in range(30):
            if proc.poll() is not None:
                _cleanup_profile(tmp_profile)
                raise BrowserAlreadyRunningError(
                    "Browser is already running. Close it first or try a different browser."
                )
            try:
                resp = await client.get(f"{cdp_url}/json/version", timeout=2)
                if resp.status_code == 200:
                    break
            except Exception:
                pass
            await asyncio.sleep(0.5)
        else:
            proc.terminate()
            _cleanup_profile(tmp_profile)
            raise CookieExtractionError("Browser did not start in time.")

        if on_status:
            on_status("Browser opened - log in to LeetCode there, then come back here.")

        cookies = await _poll_cdp_cookies(client, cdp_url, proc)

    asyncio.get_event_loop().create_task(
        _deferred_cleanup(proc, tmp_profile)
    )

    return cookies


async def _deferred_cleanup(proc: subprocess.Popen, profile_dir: str) -> None:
    """Wait for browser process to exit, then clean up the temp profile."""
    try:
        while proc.poll() is None:
            await asyncio.sleep(5)
        _cleanup_profile(profile_dir)
    except Exception:
        pass


async def _poll_cdp_cookies(
    client: httpx.AsyncClient,
    cdp_url: str,
    proc: subprocess.Popen,
) -> BrowserCookies:
    """Poll CDP for LeetCode session cookies until found or timeout."""
    for _ in range(60):  # Up to 5 minutes
        if proc.poll() is not None:
            raise CookieExtractionError("Browser was closed before logging in.")

        try:
            resp = await client.get(f"{cdp_url}/json", timeout=5)
            pages = resp.json()
            ws_url = None
            for page in pages:
                if "leetcode.com" in page.get("url", ""):
                    ws_url = page.get("webSocketDebuggerUrl")
                    break
            if not ws_url and pages:
                ws_url = pages[0].get("webSocketDebuggerUrl")

            if ws_url:
                cookies = await _get_cookies_via_ws(ws_url)
                if cookies.is_complete:
                    return cookies
        except Exception:
            pass

        await asyncio.sleep(5)

    raise CookieExtractionError("Timed out waiting for login. Please try again.")


async def _get_cookies_via_ws(ws_url: str) -> BrowserCookies:
    """Connect to CDP WebSocket and get cookies."""
    cookies = BrowserCookies()
    try:
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps({
                "id": 1,
                "method": "Network.getAllCookies",
            }))
            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            for cookie in response.get("result", {}).get("cookies", []):
                if "leetcode.com" not in cookie.get("domain", ""):
                    continue
                if cookie["name"] == "LEETCODE_SESSION":
                    cookies.leetcode_session = cookie["value"]
                elif cookie["name"] == "csrftoken":
                    cookies.csrftoken = cookie["value"]
    except Exception:
        pass
    return cookies


def _cleanup_profile(path: str) -> None:
    """Clean up temporary browser profile."""
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass
