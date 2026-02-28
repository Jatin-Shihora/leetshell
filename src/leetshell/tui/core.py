from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blessed import Terminal
    from leetshell.app import LeetCodeApp


class Screen:
    """Base class for all TUI screens.

    Subclasses must implement render() and handle_key().
    """

    def __init__(self, app: LeetCodeApp) -> None:
        self.app = app
        self.term: Terminal = app.term
        self.dirty: bool = True
        self._prev_width: int = 0
        self._prev_height: int = 0

    def render(self) -> None:
        """Write the screen contents directly to stdout."""
        raise NotImplementedError

    async def handle_key(self, key) -> None:
        """Process a keystroke. key is a blessed Keystroke object."""
        raise NotImplementedError

    def invalidate(self) -> None:
        """Mark this screen as needing a re-render."""
        self.dirty = True

    def check_resize(self) -> bool:
        """Check if terminal size changed (no SIGWINCH on Windows)."""
        w, h = self.term.width, self.term.height
        if w != self._prev_width or h != self._prev_height:
            self._prev_width = w
            self._prev_height = h
            self.invalidate()
            return True
        return False

    def run_async(self, coro) -> None:
        """Fire an async task; invalidate screen when it completes."""
        import asyncio

        async def _wrapper():
            try:
                await coro
            finally:
                self.invalidate()

        asyncio.create_task(_wrapper())

    async def on_enter(self) -> None:
        """Called when this screen becomes the active screen."""
        self.invalidate()

    async def on_exit(self) -> None:
        """Called when this screen is removed from the stack."""
        pass


# ── Terminal helpers ──────────────────────────────────────────────────────


def write_at(term: Terminal, x: int, y: int, text: str) -> None:
    """Write text at a specific (x, y) position. x=column, y=row."""
    sys.stdout.write(term.move_xy(x, y) + text)


def clear_screen(term: Terminal) -> None:
    """Clear the entire screen."""
    sys.stdout.write(term.clear)


def clear_line(term: Terminal, y: int) -> None:
    """Clear a specific line."""
    sys.stdout.write(term.move_xy(0, y) + term.clear_eol)


def draw_hline(term: Terminal, y: int, char: str = "-", width: int = 0) -> None:
    """Draw a horizontal line at row y."""
    w = width or term.width
    sys.stdout.write(term.move_xy(0, y) + char * w)


def truncate(text: str, width: int, term: Terminal | None = None) -> str:
    """Truncate PLAIN text to fit within width. Do NOT pass colored text."""
    if width <= 0:
        return ""
    text_len = len(text)
    if text_len <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def pad_right(text: str, width: int) -> str:
    """Pad PLAIN text with spaces to exact width. Do NOT pass colored text."""
    if width <= 0:
        return ""
    text = truncate(text, width)
    return text + " " * (width - len(text))


def write_columns(term: Terminal, y: int, cols: list[tuple[int, int, str, str]]) -> None:
    """Write multiple columns on a single row, clearing the full line.

    Each col is (x, width, text, color_name).
    text must be PLAIN text (no escape codes).
    color_name is a blessed attribute name like "green", "yellow", "red",
    "dim", "bold", "reverse", or "" for default.
    """
    clear_line(term, y)
    for x, w, text, color in cols:
        display = truncate(text, w)
        if color:
            try:
                fmt = getattr(term, color)
                sys.stdout.write(term.move_xy(x, y) + fmt(display))
            except (AttributeError, TypeError):
                sys.stdout.write(term.move_xy(x, y) + display)
        else:
            sys.stdout.write(term.move_xy(x, y) + display)


def write_row(term: Terminal, y: int, text: str, color: str = "",
              fill: bool = False) -> None:
    """Write a full row of PLAIN text with optional color and fill to width."""
    if fill:
        text = pad_right(text, term.width)
    if color:
        try:
            fmt = getattr(term, color)
            sys.stdout.write(term.move_xy(0, y) + fmt(text))
        except (AttributeError, TypeError):
            sys.stdout.write(term.move_xy(0, y) + text)
    else:
        sys.stdout.write(term.move_xy(0, y) + text)


def fmt(term: Terminal, color: str, text: str) -> str:
    """Safely apply terminal formatting. Falls back to plain text on failure."""
    if not color:
        return text
    try:
        return getattr(term, color)(text)
    except (AttributeError, TypeError):
        return text


def flush() -> None:
    """Flush stdout."""
    sys.stdout.flush()
