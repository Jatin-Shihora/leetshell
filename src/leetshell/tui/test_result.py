from __future__ import annotations

from leetshell.models.submission import TestResult
from leetshell.tui.core import (
    Screen, write_at, clear_screen, clear_line, pad_right, truncate, fmt, flush,
)


class TestResultScreen(Screen):
    on_dismiss = None  # callback: async (action: str | None) -> None

    def __init__(self, app, result: TestResult, title_slug: str) -> None:
        super().__init__(app)
        self._result = result
        self._title_slug = title_slug
        self._lines: list[tuple[str, str]] = []  # (color, text) pairs
        self._scroll = 0
        self._build_lines()

    def _build_lines(self) -> None:
        r = self._result
        lines = self._lines

        if r.run_success:
            passed = sum(1 for tc in r.test_cases if tc.passed)
            total = len(r.test_cases)
            color = "green" if passed == total else "yellow"
            lines.append((color, f"Test Results: {passed}/{total} passed"))
        else:
            lines.append(("red", r.status_msg))

        lines.append(("", ""))

        if r.compile_error:
            lines.append(("red", "Compile Error:"))
            for line in r.compile_error.split("\n"):
                lines.append(("red", "  " + line))
            lines.append(("", ""))

        if r.runtime_error:
            lines.append(("red", "Runtime Error:"))
            for line in r.runtime_error.split("\n"):
                lines.append(("red", "  " + line))
            lines.append(("", ""))

        for i, tc in enumerate(r.test_cases):
            icon = "PASS" if tc.passed else "FAIL"
            icon_color = "green" if tc.passed else "red"
            lines.append((icon_color, f"  {icon}  Case {i + 1}"))
            if tc.input_data:
                lines.append(("", f"    input:    {tc.input_data}"))
            lines.append(("", f"    expected: {tc.expected}"))
            lines.append(("", f"    output:   {tc.actual}"))
            lines.append(("", ""))

        if r.runtime:
            lines.append(("dim", f"runtime: {r.runtime}  memory: {r.memory}"))

    def render(self) -> None:
        t = self.term
        clear_screen(t)
        w = t.width
        h = t.height

        # Title
        write_at(t, 0, 0, fmt(t, "bold", "Test Results"))

        # Scrollable content
        body_start = 2
        body_end = h - 2
        visible = body_end - body_start

        for i in range(visible):
            idx = self._scroll + i
            row_y = body_start + i
            if idx >= len(self._lines):
                clear_line(t, row_y)
                continue

            color, text = self._lines[idx]
            display = truncate(text, w)
            write_at(t, 0, row_y, fmt(t, color, display))

        # Status bar
        hints = "[s] submit  [e] edit  [esc] back  [j/k] scroll"
        write_at(t, 0, h - 1, fmt(t, "dim", pad_right(hints, w)))
        flush()

    async def handle_key(self, key) -> None:
        if key == "s":
            await self._dismiss("submit")
        elif key == "e":
            await self._dismiss("edit")
        elif key.name == "KEY_ESCAPE":
            await self._dismiss(None)
        elif key == "j" or key.name == "KEY_DOWN":
            max_scroll = max(0, len(self._lines) - (self.term.height - 4))
            if self._scroll < max_scroll:
                self._scroll += 1
                self.invalidate()
        elif key == "k" or key.name == "KEY_UP":
            if self._scroll > 0:
                self._scroll -= 1
                self.invalidate()
        elif key.name == "KEY_PGDOWN":
            max_scroll = max(0, len(self._lines) - (self.term.height - 4))
            self._scroll = min(max_scroll, self._scroll + 20)
            self.invalidate()
        elif key.name == "KEY_PGUP":
            self._scroll = max(0, self._scroll - 20)
            self.invalidate()

    async def _dismiss(self, action: str | None) -> None:
        callback = self.on_dismiss
        await self.app.pop_screen()
        if callback:
            await callback(action)
