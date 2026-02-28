from __future__ import annotations

import asyncio
import logging
import os
import sys
import traceback

from blessed import Terminal

from leetshell.api.auth import validate_session
from leetshell.api.client import LeetCodeClient
from leetshell.api.problems import ProblemService
from leetshell.api.submissions import SubmissionService
from leetshell.config import load_config, save_config
from leetshell.constants import CONFIG_DIR
from leetshell.models.user import Credentials, UserConfig
from leetshell.tui.core import Screen, clear_screen, flush

# Set up file logger for debugging
_log_file = CONFIG_DIR / "debug.log"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("leetshell")
logger.setLevel(logging.DEBUG)
_handler = logging.FileHandler(str(_log_file), mode="w", encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(_handler)


class LeetCodeApp:
    """Application controller - manages screen stack and event loop."""

    def __init__(self) -> None:
        # Enable VT100 escape processing on Windows
        if sys.platform == "win32":
            os.system("")
        # Ensure stdout can handle Unicode (box-drawing chars, etc.)
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        self.term = Terminal()
        self.user_config: UserConfig = UserConfig()
        self.client: LeetCodeClient = LeetCodeClient()
        self.problem_service: ProblemService = ProblemService(self.client)
        self.submission_service: SubmissionService = SubmissionService(self.client)
        self.username: str = ""
        self._screen_stack: list[Screen] = []
        self._running: bool = False
        self._notification: str = ""
        self._notification_expiry: float = 0
        logger.info("App initialized, terminal %dx%d, is_tty=%s, colors=%d",
                     self.term.width, self.term.height,
                     self.term.is_a_tty, self.term.number_of_colors)

    @property
    def current_screen(self) -> Screen | None:
        return self._screen_stack[-1] if self._screen_stack else None

    async def push_screen(self, screen: Screen) -> None:
        """Push a new screen onto the stack."""
        logger.info("push_screen: %s (stack depth: %d -> %d)",
                     type(screen).__name__, len(self._screen_stack),
                     len(self._screen_stack) + 1)
        self._screen_stack.append(screen)
        clear_screen(self.term)
        flush()
        await screen.on_enter()

    async def pop_screen(self) -> None:
        """Pop the current screen and return to previous."""
        if self._screen_stack:
            old = self._screen_stack.pop()
            logger.info("pop_screen: %s (stack depth: %d)",
                         type(old).__name__, len(self._screen_stack))
            await old.on_exit()
        if self._screen_stack:
            clear_screen(self.term)
            flush()
            await self._screen_stack[-1].on_enter()
        else:
            logger.info("pop_screen: stack empty, exiting")
            self.exit()

    async def replace_screen(self, screen: Screen) -> None:
        """Replace the current screen."""
        if self._screen_stack:
            old = self._screen_stack.pop()
            logger.info("replace_screen: %s -> %s",
                         type(old).__name__, type(screen).__name__)
            await old.on_exit()
        await self.push_screen(screen)

    def notify(self, msg: str, duration: float = 3.0) -> None:
        """Show a temporary notification on the status line."""
        import time
        self._notification = msg
        self._notification_expiry = time.time() + duration
        logger.info("notify: %s", msg)
        if self.current_screen:
            self.current_screen.invalidate()

    def get_notification(self) -> str:
        """Get current notification if not expired."""
        import time
        if self._notification and time.time() < self._notification_expiry:
            return self._notification
        self._notification = ""
        return ""

    def exit(self) -> None:
        """Signal the event loop to stop."""
        logger.info("exit() called")
        self._running = False

    async def _startup(self) -> None:
        """Initialize and show the first screen."""
        self.user_config = load_config()
        logger.info("Config loaded, session valid: %s, language: %s",
                     self.user_config.credentials.is_valid(),
                     self.user_config.preferences.language)
        if self.user_config.credentials.is_valid():
            self.client.update_credentials(
                self.user_config.credentials.leetcode_session,
                self.user_config.credentials.csrftoken,
            )
            await self._check_session()
        else:
            await self._show_login()

    async def _check_session(self) -> None:
        """Validate the saved session."""
        try:
            username = await validate_session(self.client)
        except Exception as e:
            # Network error - trust saved credentials and proceed
            logger.warning("Session validation failed (network): %s", e)
            await self._goto_problem_list()
            return
        if username:
            self.username = username
            logger.info("Session valid, user: %s", username)
            await self._goto_problem_list()
        else:
            logger.info("Session invalid, showing login")
            await self._show_login()

    async def _show_login(self) -> None:
        from leetshell.tui.login import LoginScreen
        await self.push_screen(LoginScreen(self))

    async def on_login_result(self, result: Credentials | None) -> None:
        """Called by LoginScreen when login completes."""
        if result is None:
            self.exit()
            return
        self.user_config.credentials = result
        save_config(self.user_config)
        self.client.update_credentials(result.leetcode_session, result.csrftoken)
        await self._check_session()

    async def _goto_problem_list(self) -> None:
        from leetshell.tui.problem_list import ProblemListScreen
        await self.replace_screen(ProblemListScreen(self))

    async def logout(self) -> None:
        """Clear credentials and return to login screen."""
        self.user_config.credentials = Credentials()
        save_config(self.user_config)
        self.username = ""
        logger.info("Logged out, clearing credentials")
        # Pop all screens and show login
        while self._screen_stack:
            old = self._screen_stack.pop()
            await old.on_exit()
        await self._show_login()

    def show_login_on_auth_error(self) -> None:
        """Called by screens when an auth error is detected."""
        self.notify("Session expired. Please log in again.")

        async def _relogin():
            while self._screen_stack:
                old = self._screen_stack.pop()
                await old.on_exit()
            await self._show_login()

        asyncio.create_task(_relogin())

    async def run(self) -> None:
        """Main event loop."""
        self._running = True
        t = self.term

        with t.fullscreen(), t.cbreak(), t.hidden_cursor():
            clear_screen(t)
            flush()

            try:
                await self._startup()
            except Exception:
                logger.error("Startup failed:\n%s", traceback.format_exc())
                return

            while self._running:
                screen = self.current_screen
                if screen is None:
                    break

                # Check for resize (no SIGWINCH on Windows)
                screen.check_resize()

                # Render if dirty
                if screen.dirty:
                    screen.dirty = False
                    try:
                        screen.render()
                        flush()
                    except Exception:
                        logger.error("Render error in %s:\n%s",
                                     type(screen).__name__,
                                     traceback.format_exc())

                # Let async tasks run (critical for API calls)
                await asyncio.sleep(0)

                # Read key with timeout (non-blocking via thread)
                try:
                    key = await asyncio.to_thread(t.inkey, timeout=0.05)
                except Exception:
                    logger.error("inkey error:\n%s", traceback.format_exc())
                    await asyncio.sleep(0.05)
                    continue

                if key:
                    logger.debug("key: %r name=%s is_seq=%s",
                                 str(key), key.name, key.is_sequence)
                    try:
                        await screen.handle_key(key)
                    except Exception:
                        logger.error("Key handler error in %s:\n%s",
                                     type(screen).__name__,
                                     traceback.format_exc())

        # Cleanup
        logger.info("Event loop ended, cleaning up")
        try:
            await self.client.close()
        except Exception:
            pass
