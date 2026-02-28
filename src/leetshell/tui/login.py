from __future__ import annotations

import asyncio
import sys

from leetshell.api.auth import validate_session
from leetshell.api.client import LeetCodeClient
from leetshell.browser_cookies import (
    extract_cookies,
    find_browser_exe,
    get_all_browser_names,
    get_fallback_browser,
    try_read_cookies_from_any_browser,
    BrowserAlreadyRunningError,
    CookieExtractionError,
)
from leetshell.models.user import Credentials
from leetshell.tui.core import (
    Screen, write_at, clear_screen, clear_line, pad_right, write_row, fmt, flush,
)


_LOGO = [
    r"  _                _    ____          _        ",
    r" | |    ___   ___ | |_ / ___|___   __| | ___   ",
    r" | |   / _ \ / _ \| __| |   / _ \ / _` |/ _ \  ",
    r" | |__|  __/|  __/| |_| |__| (_) | (_| |  __/  ",
    r" |_____\___| \___| \__|\____\___/ \__,_|\___|  ",
    r"      ____  _   _ _____ _     _     ",
    r"     / ___|| | | | ____| |   | |    ",
    r"     \___ \| |_| |  _| | |   | |    ",
    r"      ___) |  _  | |___| |___| |___ ",
    r"     |____/|_| |_|_____|_____|_____|",
]

_LOGO_SMALL = [
    r"  _         _    ___         _       ",
    r" | |___ ___| |_ / __|___  __| |___   ",
    r" | / -_) -_)  _| (__/ _ \/ _` / -_)  ",
    r" |_\___\___|\__|\___\___/\__,_\___|  ",
    r"       _        _ _  ",
    r"  ___ | |_  ___| | | ",
    r" (_-< | ' \/ -_) | | ",
    r" /__/ |_||_\___|_|_| ",
]


class LoginScreen(Screen):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._step = "method"
        self._cursor = 0
        self._options: list[str] = []
        self._status = ""
        self._status_color = ""
        self._input_label = ""
        self._input_buffer = ""
        self._input_masked = False
        self._input_mode = False
        self._session_value = ""
        self._busy = False

    async def on_enter(self) -> None:
        self._show_method_step()

    # ── Step transitions ─────────────────────────────────────────────

    def _show_method_step(self) -> None:
        self._step = "method"
        self._options = ["Login via Browser", "Manual Cookie Entry"]
        self._cursor = 0
        self._status = ""
        self._input_mode = False
        self._input_label = ""
        self.invalidate()

    def _show_browser_step(self) -> None:
        self._step = "browser"
        self._options = get_all_browser_names()
        self._cursor = 0
        self._status = ""
        self._input_mode = False
        self.invalidate()

    def _show_manual_session_step(self) -> None:
        self._step = "manual_session"
        self._options = []
        self._input_label = "Paste cookies from DevTools (F12) > Application > Cookies"
        self._input_buffer = ""
        self._input_masked = True
        self._input_mode = True
        self._status = ""
        self.invalidate()

    def _show_manual_csrf_step(self) -> None:
        self._step = "manual_csrf"
        self._input_buffer = ""
        self._input_masked = True
        self._input_mode = True
        self.invalidate()

    def _set_status(self, msg: str, color: str = "") -> None:
        self._status = msg
        self._status_color = color
        self.invalidate()

    # ── Rendering ─────────────────────────────────────────────────────

    def render(self) -> None:
        t = self.term
        w = t.width
        h = t.height

        clear_screen(t)

        # Pick logo that fits the terminal width
        logo = _LOGO if w >= 56 else _LOGO_SMALL

        # Center the logo horizontally
        logo_w = max(len(line) for line in logo)
        x_off = max(0, (w - logo_w) // 2)

        row = 1
        # Draw "LeetCode" part (first 5 lines) in yellow
        leet_lines = len(logo) // 2
        for i in range(leet_lines):
            write_at(t, x_off, row, fmt(t, "yellow", logo[i]))
            row += 1

        # Draw "TERMINAL" part (remaining lines) in bright_cyan
        for i in range(leet_lines, len(logo)):
            write_at(t, x_off, row, fmt(t, "bright_cyan", logo[i]))
            row += 1

        # Tagline
        row += 1
        tagline = "solve problems without leaving your terminal"
        tag_x = max(0, (w - len(tagline)) // 2)
        write_at(t, tag_x, row, fmt(t, "dim", tagline))
        row += 2

        # Divider
        div_w = min(logo_w, w - 4)
        div_x = max(0, (w - div_w) // 2)
        write_at(t, div_x, row, fmt(t, "dim", "-" * div_w))
        row += 2

        if self._options:
            if self._step == "browser":
                write_at(t, 2, row, "Pick a browser:")
                row += 1

            for i, option in enumerate(self._options):
                if i == self._cursor:
                    text = f"  > {option}"
                    sys.stdout.write(
                        t.move_xy(2, row) + fmt(t, "reverse", pad_right(text, w - 4))
                    )
                else:
                    write_at(t, 2, row, f"    {option}")
                row += 1

        if self._input_mode:
            row += 1
            if self._input_label:
                write_at(t, 2, row, self._input_label)
                row += 1

            if self._step == "manual_session":
                prompt = "LEETCODE_SESSION: "
            else:
                prompt = "csrftoken: "
            display = "*" * len(self._input_buffer) if self._input_masked else self._input_buffer
            write_at(t, 2, row, prompt + display + fmt(t, "reverse", " "))
            row += 1

        if self._status:
            row += 1
            color = self._status_color
            write_at(t, 2, row, fmt(t, color, self._status))

        # Keybinding hints at bottom
        hints = "arrows navigate  enter select  esc back"
        write_row(t, h - 1, " " + hints, "dim", fill=True)
        flush()

    # ── Key handling ─────────────────────────────────────────────────

    async def handle_key(self, key) -> None:
        if self._busy:
            return

        # Input mode
        if self._input_mode:
            if key.name == "KEY_ESCAPE":
                self._input_mode = False
                self._show_method_step()
            elif key.name == "KEY_ENTER":
                await self._on_input_submit()
            elif key.name == "KEY_BACKSPACE" or key.name == "KEY_DELETE":
                if self._input_buffer:
                    self._input_buffer = self._input_buffer[:-1]
                    self.invalidate()
            elif key and not key.is_sequence:
                self._input_buffer += key
                self.invalidate()
            return

        # Menu mode
        if key.name == "KEY_UP" or key == "k":
            if self._options:
                self._cursor = (self._cursor - 1) % len(self._options)
                self.invalidate()
        elif key.name == "KEY_DOWN" or key == "j":
            if self._options:
                self._cursor = (self._cursor + 1) % len(self._options)
                self.invalidate()
        elif key.name == "KEY_ENTER":
            await self._on_menu_select()
        elif key.name == "KEY_ESCAPE" or key == "q":
            if self._step in ("browser", "manual_session", "manual_csrf"):
                self._show_method_step()
            else:
                await self.app.on_login_result(None)

    async def _on_menu_select(self) -> None:
        if self._step == "method":
            if self._cursor == 0:
                self._show_browser_step()
            else:
                self._show_manual_session_step()
        elif self._step == "browser":
            browser_name = self._options[self._cursor]
            self._busy = True
            asyncio.create_task(self._try_browser(browser_name))

    async def _on_input_submit(self) -> None:
        value = self._input_buffer.strip()
        if not value:
            return

        if self._step == "manual_session":
            self._session_value = value
            self._set_status("LEETCODE_SESSION saved.", "green")
            self._show_manual_csrf_step()
        elif self._step == "manual_csrf":
            self._input_mode = False
            self._busy = True
            asyncio.create_task(self._validate_manual(self._session_value, value))

    # ── Browser login flow ────────────────────────────────────────────

    async def _try_browser(self, browser_name: str, _tried: set | None = None) -> None:
        if _tried is None:
            _tried = set()
        _tried.add(browser_name)

        try:
            exe = find_browser_exe(browser_name)

            if exe is None:
                fallback = get_fallback_browser(browser_name)
                if fallback and fallback not in _tried:
                    self._set_status(
                        f"Could not find {browser_name}. Trying {fallback} instead...",
                        "yellow",
                    )
                    await asyncio.sleep(1)
                    await self._try_browser(fallback, _tried)
                    return
                self._set_status(
                    f"Could not find {browser_name} or any other browser.",
                    "red",
                )
                self._busy = False
                self._show_browser_step()
                return

            self._set_status(f"Checking {browser_name}...", "dim")

            cookies = await extract_cookies(
                browser_name,
                on_status=lambda msg: self._set_status(msg, "dim"),
            )

            if not cookies.is_complete:
                self._set_status(
                    "Could not find session cookies. Did you log in?",
                    "red",
                )
                self._busy = False
                self._show_browser_step()
                return

            self._set_status("Validating session...", "dim")
            creds = Credentials(
                leetcode_session=cookies.leetcode_session,
                csrftoken=cookies.csrftoken,
            )
            client = LeetCodeClient(creds.leetcode_session, creds.csrftoken)
            try:
                username = await validate_session(client)
                if username:
                    self._set_status(f"Logged in as {username}", "green")
                    await asyncio.sleep(0.5)
                    self._busy = False
                    await self.app.on_login_result(creds)
                    return
                else:
                    self._set_status("Session invalid. Try again.", "red")
            finally:
                await client.close()

        except BrowserAlreadyRunningError:
            self._set_status(
                f"{browser_name} is running - checking for saved session...",
                "yellow",
            )
            await asyncio.sleep(0.5)
            disk_cookies, source = try_read_cookies_from_any_browser()
            if disk_cookies and disk_cookies.is_complete:
                self._set_status(f"Found session in {source}. Validating...", "dim")
                creds = Credentials(
                    leetcode_session=disk_cookies.leetcode_session,
                    csrftoken=disk_cookies.csrftoken,
                )
                client = LeetCodeClient(creds.leetcode_session, creds.csrftoken)
                try:
                    username = await validate_session(client)
                    if username:
                        self._set_status(f"Logged in as {username}", "green")
                        await asyncio.sleep(0.5)
                        self._busy = False
                        await self.app.on_login_result(creds)
                        return
                finally:
                    await client.close()

            fallback = get_fallback_browser(_tried)
            if fallback and fallback not in _tried:
                self._set_status(
                    f"Opening {fallback} instead - please log in there...",
                    "yellow",
                )
                await asyncio.sleep(1)
                await self._try_browser(fallback, _tried)
                return
            self._set_status(
                "All browsers are running. Close one and try again, "
                "or press Esc and use manual cookie entry.",
                "red",
            )
        except CookieExtractionError as e:
            self._set_status(str(e), "red")
        except Exception as e:
            self._set_status(f"Error: {e}", "red")

        self._busy = False
        self._show_browser_step()

    # ── Manual cookie entry ───────────────────────────────────────────

    async def _validate_manual(self, session_val: str, csrf_val: str) -> None:
        self._set_status("Validating session...", "dim")

        client = LeetCodeClient(session_val, csrf_val)
        try:
            username = await validate_session(client)
            if username:
                self._set_status(f"Logged in as {username}", "green")
                creds = Credentials(leetcode_session=session_val, csrftoken=csrf_val)
                await asyncio.sleep(0.5)
                self._busy = False
                await self.app.on_login_result(creds)
            else:
                self._set_status("Invalid cookies. Try again.", "red")
                self._busy = False
                self._show_manual_session_step()
        except Exception as e:
            self._set_status(f"Error: {e}", "red")
            self._busy = False
            self._show_manual_session_step()
        finally:
            await client.close()
