from __future__ import annotations

import asyncio
import sys

from leetshell.api.client import AuthenticationError
from leetshell.models.problem import ProblemSummary
from leetshell.tui.core import (
    Screen, write_at, clear_screen, clear_line, pad_right, truncate,
    write_row, fmt, flush,
)


# Column widths
COL_STATUS = 3
COL_ID = 7
COL_DIFF = 12
COL_AC = 8

_DIFF_CYCLE = ["", "EASY", "MEDIUM", "HARD"]
_DIFF_DISPLAY = {"": "All", "EASY": "Easy", "MEDIUM": "Medium", "HARD": "Hard"}
_DIFF_COLOR = {"Easy": "green", "Medium": "yellow", "Hard": "red"}
_STATUS_ICON = {"ac": "v", "notac": "x"}
_STATUS_COLOR = {"ac": "green", "notac": "yellow"}


class ProblemListScreen(Screen):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._problems: list[ProblemSummary] = []
        self._total = 0
        self._skip = 0
        self._limit = 50
        self._difficulty = ""
        self._search = ""
        self._cursor = 0
        self._scroll = 0  # first visible problem index
        self._loading = True
        self._searching = False
        self._search_buffer = ""

    async def on_enter(self) -> None:
        self.invalidate()
        if not self._problems:
            self._loading = True
            asyncio.create_task(self._fetch_problems())

    # ── Data fetching ────────────────────────────────────────────────

    async def _fetch_problems(self) -> None:
        self._loading = True
        self.invalidate()
        try:
            problems, total = await self.app.problem_service.get_problem_list(
                limit=self._limit,
                skip=self._skip,
                difficulty=self._difficulty,
                search=self._search,
            )
            self._problems = problems
            self._total = total
            self._loading = False
            self._cursor = 0
            self._scroll = 0
            self.invalidate()
        except AuthenticationError:
            self._loading = False
            self.app.show_login_on_auth_error()
        except Exception as e:
            self._loading = False
            self.app.notify(f"Error: {e}")
            self.invalidate()

    # ── Scroll helpers ────────────────────────────────────────────────

    def _visible_rows(self) -> int:
        """Number of visible table body rows."""
        return max(1, self.term.height - 4)  # rows 2..(h-2)

    def _ensure_cursor_visible(self) -> None:
        """Adjust scroll so the cursor is within the visible area."""
        visible = self._visible_rows()
        if self._cursor < self._scroll:
            self._scroll = self._cursor
        elif self._cursor >= self._scroll + visible:
            self._scroll = self._cursor - visible + 1

    # ── Rendering ─────────────────────────────────────────────────────

    def render(self) -> None:
        t = self.term
        w = t.width
        h = t.height

        # Row 0: Filter bar
        if self._searching:
            filter_text = "Search: " + self._search_buffer
            cursor_char = fmt(t, "reverse", " ")
            filter_display = pad_right(filter_text, w - 1)
            sys.stdout.write(t.move_xy(0, 0) + filter_display + cursor_char)
        else:
            diff_display = _DIFF_DISPLAY[self._difficulty]
            search_display = f'  "{self._search}"' if self._search else ""
            filter_text = f" Difficulty: {diff_display}{search_display}"
            write_row(t, 0, filter_text, "reverse", fill=True)

        if self._loading:
            for row_y in range(1, h):
                clear_line(t, row_y)
            write_at(t, w // 2 - 5, h // 2, fmt(t, "dim", "loading..."))
            flush()
            return

        # Row 1: Table header
        col_title_w = max(w - COL_STATUS - COL_ID - COL_DIFF - COL_AC, 10)
        self._render_header(t, 1, w, col_title_w)

        # Rows 2..(h-2): Table body with scroll
        body_start = 2
        body_end = h - 2
        visible = body_end - body_start

        self._ensure_cursor_visible()

        for i in range(visible):
            problem_idx = self._scroll + i
            row_y = body_start + i
            if problem_idx >= len(self._problems):
                clear_line(t, row_y)
                continue
            self._render_row(t, row_y, self._problems[problem_idx], col_title_w, w,
                             is_selected=(problem_idx == self._cursor))

        # Bottom status bar
        page = self._skip // self._limit + 1
        total_pages = max(1, (self._total + self._limit - 1) // self._limit)
        info = f" {len(self._problems)} of {self._total}  pg {page}/{total_pages}"
        if self._difficulty:
            info += f"  [{self._difficulty.lower()}]"
        if self._search:
            info += f'  "{self._search}"'
        hints = "j/k scroll  pgdn/pgup page  / search  d difficulty  r refresh  enter open  L logout  esc quit"
        status_line = info + "  |  " + hints
        write_row(t, h - 1, status_line, "dim", fill=True)
        flush()

    def _render_header(self, t, y: int, w: int, col_title_w: int) -> None:
        x = 0
        sys.stdout.write(t.move_xy(0, y) + t.clear_eol)
        sys.stdout.write(t.move_xy(x, y) + fmt(t, "bold", pad_right(" ", COL_STATUS)))
        x += COL_STATUS
        sys.stdout.write(t.move_xy(x, y) + fmt(t, "bold", pad_right("#", COL_ID)))
        x += COL_ID
        sys.stdout.write(t.move_xy(x, y) + fmt(t, "bold", pad_right("Title", col_title_w)))
        x += col_title_w
        sys.stdout.write(t.move_xy(x, y) + fmt(t, "bold", pad_right("Difficulty", COL_DIFF)))
        x += COL_DIFF
        sys.stdout.write(t.move_xy(x, y) + fmt(t, "bold", pad_right("AC%", COL_AC)))

    def _render_row(self, t, y: int, p: ProblemSummary, col_title_w: int,
                    w: int, is_selected: bool) -> None:
        if is_selected:
            status_icon = "$" if p.paid_only else _STATUS_ICON.get(p.status, " ")
            plain_line = (
                pad_right(status_icon, COL_STATUS)
                + pad_right(p.frontend_id, COL_ID)
                + pad_right(truncate(p.title, col_title_w - 1), col_title_w)
                + pad_right(p.difficulty, COL_DIFF)
                + pad_right(f"{p.ac_rate:.1f}%", COL_AC)
            )
            sys.stdout.write(
                t.move_xy(0, y) + fmt(t, "reverse", pad_right(plain_line, w))
            )
            return

        x = 0
        sys.stdout.write(t.move_xy(0, y) + t.clear_eol)

        # Status icon
        if p.paid_only:
            sys.stdout.write(t.move_xy(x, y) + pad_right("$", COL_STATUS))
        elif p.status in _STATUS_COLOR:
            icon = _STATUS_ICON[p.status]
            sys.stdout.write(t.move_xy(x, y) + fmt(t, _STATUS_COLOR[p.status], icon) + " " * (COL_STATUS - 1))
        else:
            sys.stdout.write(t.move_xy(x, y) + " " * COL_STATUS)
        x += COL_STATUS

        sys.stdout.write(t.move_xy(x, y) + pad_right(p.frontend_id, COL_ID))
        x += COL_ID

        sys.stdout.write(t.move_xy(x, y) + pad_right(truncate(p.title, col_title_w - 1), col_title_w))
        x += col_title_w

        diff_color = _DIFF_COLOR.get(p.difficulty, "")
        sys.stdout.write(t.move_xy(x, y) + fmt(t, diff_color, pad_right(p.difficulty, COL_DIFF)))
        x += COL_DIFF

        sys.stdout.write(t.move_xy(x, y) + pad_right(f"{p.ac_rate:.1f}%", COL_AC))

    # ── Key handling ──────────────────────────────────────────────────

    async def handle_key(self, key) -> None:
        # Search input mode
        if self._searching:
            if key.name == "KEY_ESCAPE":
                self._searching = False
                self.invalidate()
            elif key.name == "KEY_ENTER":
                self._search = self._search_buffer
                self._searching = False
                self._skip = 0
                asyncio.create_task(self._fetch_problems())
            elif key.name == "KEY_BACKSPACE" or key.name == "KEY_DELETE":
                if self._search_buffer:
                    self._search_buffer = self._search_buffer[:-1]
                    self.invalidate()
            elif key and not key.is_sequence:
                self._search_buffer += key
                self.invalidate()
            return

        # Normal mode
        if key == "j" or key.name == "KEY_DOWN":
            if self._problems and self._cursor < len(self._problems) - 1:
                self._cursor += 1
                self.invalidate()
        elif key == "k" or key.name == "KEY_UP":
            if self._cursor > 0:
                self._cursor -= 1
                self.invalidate()
        elif key.name == "KEY_PGDOWN":
            if self._skip + self._limit < self._total:
                self._skip += self._limit
                asyncio.create_task(self._fetch_problems())
        elif key.name == "KEY_PGUP":
            if self._skip > 0:
                self._skip = max(0, self._skip - self._limit)
                asyncio.create_task(self._fetch_problems())
        elif key == "/":
            self._searching = True
            self._search_buffer = self._search
            self.invalidate()
        elif key == "d":
            idx = (_DIFF_CYCLE.index(self._difficulty) + 1) % len(_DIFF_CYCLE)
            self._difficulty = _DIFF_CYCLE[idx]
            self._skip = 0
            asyncio.create_task(self._fetch_problems())
        elif key == "r":
            self._skip = 0
            asyncio.create_task(self._fetch_problems())
        elif key.name == "KEY_ENTER":
            await self._open_problem()
        elif key == "L":
            await self.app.logout()
        elif key.name == "KEY_ESCAPE" or key == "q":
            self.app.exit()

    async def _open_problem(self) -> None:
        if not self._problems or self._cursor >= len(self._problems):
            return
        p = self._problems[self._cursor]
        if p.paid_only:
            self.app.notify("Premium problem -- not available.")
            return
        from leetshell.tui.problem_detail import ProblemDetailScreen
        await self.app.push_screen(ProblemDetailScreen(self.app, p.title_slug))
