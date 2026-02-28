from __future__ import annotations

from leetshell.constants import STATUS_COLORS, STATUS_ACCEPTED
from leetshell.models.submission import SubmissionResult
from leetshell.tui.core import (
    Screen, write_at, clear_screen, clear_line, pad_right, truncate, fmt, flush,
)


class SubmissionResultScreen(Screen):
    on_dismiss = None  # callback: async (action: str | None) -> None

    def __init__(self, app, result: SubmissionResult) -> None:
        super().__init__(app)
        self._result = result
        self._lines: list[tuple[str, str]] = []  # (color, text) pairs
        self._scroll = 0
        self._build_lines()

    def _build_lines(self) -> None:
        r = self._result
        lines = self._lines
        color = STATUS_COLORS.get(r.status_code, "red")

        lines.append((color, r.display_status))
        lines.append(("", ""))

        if r.accepted:
            lines.append(("", f"  tests passed:  {r.total_correct}/{r.total_testcases}"))
            lines.append(("", f"  runtime:       {r.runtime} (faster than {r.runtime_percentile:.1f}%)"))
            lines.append(("", f"  memory:        {r.memory} (less than {r.memory_percentile:.1f}%)"))
        else:
            lines.append(("", f"  tests passed:  {r.total_correct}/{r.total_testcases}"))
            if r.runtime:
                lines.append(("", f"  runtime:       {r.runtime}"))

            if r.compile_error:
                lines.append(("", ""))
                lines.append(("red", "Compile Error:"))
                for line in r.compile_error.split("\n"):
                    lines.append(("red", "  " + line))

            if r.runtime_error:
                lines.append(("", ""))
                lines.append(("red", "Runtime Error:"))
                for line in r.runtime_error.split("\n"):
                    lines.append(("red", "  " + line))

            if r.input_data:
                lines.append(("", ""))
                lines.append(("", f"  input:     {r.input_data}"))
            if r.expected_output:
                lines.append(("", f"  expected:  {r.expected_output}"))
            if r.code_output:
                lines.append(("", f"  output:    {r.code_output}"))

    def render(self) -> None:
        t = self.term
        clear_screen(t)
        w = t.width
        h = t.height

        # Title
        write_at(t, 0, 0, fmt(t, "bold", "Submission Result"))

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
        hints = "[esc] back to problem  [q] problem list  [j/k] scroll"
        write_at(t, 0, h - 1, fmt(t, "dim", pad_right(hints, w)))
        flush()

    async def handle_key(self, key) -> None:
        if key.name == "KEY_ESCAPE":
            await self._dismiss("problem")
        elif key == "q":
            await self._dismiss("list")
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
