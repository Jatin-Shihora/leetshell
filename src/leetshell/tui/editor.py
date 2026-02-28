from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from pygments import lex
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.token import Token

if TYPE_CHECKING:
    from blessed import Terminal

from leetshell.tui.core import fmt

# Map Pygments token types to blessed color names
_TOKEN_COLORS = {
    Token.Keyword: "cyan",
    Token.Keyword.Constant: "cyan",
    Token.Keyword.Declaration: "cyan",
    Token.Keyword.Namespace: "cyan",
    Token.Keyword.Pseudo: "cyan",
    Token.Keyword.Reserved: "cyan",
    Token.Keyword.Type: "cyan",
    Token.Name.Builtin: "blue",
    Token.Name.Builtin.Pseudo: "blue",
    Token.Name.Class: "yellow",
    Token.Name.Decorator: "magenta",
    Token.Name.Exception: "yellow",
    Token.Name.Function: "yellow",
    Token.Name.Function.Magic: "yellow",
    Token.Literal.String: "green",
    Token.Literal.String.Affix: "green",
    Token.Literal.String.Backtick: "green",
    Token.Literal.String.Char: "green",
    Token.Literal.String.Delimiter: "green",
    Token.Literal.String.Doc: "green",
    Token.Literal.String.Double: "green",
    Token.Literal.String.Escape: "bright_green",
    Token.Literal.String.Heredoc: "green",
    Token.Literal.String.Interpol: "bright_green",
    Token.Literal.String.Other: "green",
    Token.Literal.String.Regex: "green",
    Token.Literal.String.Single: "green",
    Token.Literal.String.Symbol: "green",
    Token.Literal.Number: "magenta",
    Token.Literal.Number.Bin: "magenta",
    Token.Literal.Number.Float: "magenta",
    Token.Literal.Number.Hex: "magenta",
    Token.Literal.Number.Integer: "magenta",
    Token.Literal.Number.Oct: "magenta",
    Token.Comment: "bright_black",
    Token.Comment.Hashbang: "bright_black",
    Token.Comment.Multiline: "bright_black",
    Token.Comment.Preproc: "bright_black",
    Token.Comment.PreprocFile: "bright_black",
    Token.Comment.Single: "bright_black",
    Token.Comment.Special: "bright_black",
    Token.Operator: "red",
    Token.Operator.Word: "cyan",
    Token.Punctuation: "white",
    Token.Name.Tag: "cyan",
    Token.Name.Attribute: "yellow",
}


def _get_color(token_type) -> str:
    """Walk up the token hierarchy to find a color."""
    tt = token_type
    while tt:
        if tt in _TOKEN_COLORS:
            return _TOKEN_COLORS[tt]
        tt = tt.parent
    return ""


class CodeEditor:
    """Buffer-based code editor with Pygments syntax highlighting.

    This is a component, not a Screen. It renders within a given
    rectangular area and handles keystrokes passed to it.
    """

    def __init__(self, term: Terminal, lang_name: str = "python") -> None:
        self.term = term
        self._lines: list[str] = [""]
        self._cursor_row: int = 0
        self._cursor_col: int = 0
        self._scroll_row: int = 0
        self._scroll_col: int = 0
        self._lang_name: str = lang_name
        self._lexer = self._make_lexer(lang_name)
        self._highlighted: list[list[tuple[str, str]]] = []
        self._highlight_dirty: bool = True
        self.dirty: bool = True
        self._gutter_width: int = 4
        # Selection: anchor is where Shift+move started; None = no selection
        self._sel_anchor: tuple[int, int] | None = None
        # Undo/redo stacks: each entry is (lines_copy, cursor_row, cursor_col)
        self._undo_stack: list[tuple[list[str], int, int]] = []
        self._redo_stack: list[tuple[list[str], int, int]] = []
        self._max_undo: int = 200

    @staticmethod
    def _make_lexer(lang_name: str):
        try:
            return get_lexer_by_name(lang_name, stripnl=False, ensurenl=False)
        except Exception:
            return TextLexer(stripnl=False, ensurenl=False)

    def set_language(self, lang_name: str) -> None:
        self._lang_name = lang_name
        self._lexer = self._make_lexer(lang_name)
        self._highlight_dirty = True
        self.dirty = True

    def set_text(self, text: str) -> None:
        self._lines = text.split("\n") if text else [""]
        self._cursor_row = 0
        self._cursor_col = 0
        self._scroll_row = 0
        self._scroll_col = 0
        self._sel_anchor = None
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._highlight_dirty = True
        self.dirty = True

    def get_text(self) -> str:
        return "\n".join(self._lines)

    @property
    def line_count(self) -> int:
        return len(self._lines)

    # ── Selection ─────────────────────────────────────────────────────

    def _sel_range(self) -> tuple[tuple[int, int], tuple[int, int]] | None:
        """Return ((start_row, start_col), (end_row, end_col)) or None."""
        if self._sel_anchor is None:
            return None
        anchor = self._sel_anchor
        cursor = (self._cursor_row, self._cursor_col)
        if anchor == cursor:
            return None
        return (anchor, cursor) if anchor < cursor else (cursor, anchor)

    def _in_selection(self, row: int, col: int) -> bool:
        """Check if (row, col) is within the selected range."""
        sel = self._sel_range()
        if sel is None:
            return False
        (sr, sc), (er, ec) = sel
        if row < sr or row > er:
            return False
        if row == sr and row == er:
            return sc <= col < ec
        if row == sr:
            return col >= sc
        if row == er:
            return col < ec
        return True

    def _delete_selection(self) -> bool:
        """Delete selected text. Returns True if there was a selection."""
        sel = self._sel_range()
        if sel is None:
            return False
        self._save_undo()
        (sr, sc), (er, ec) = sel
        if sr == er:
            line = self._lines[sr]
            self._lines[sr] = line[:sc] + line[ec:]
        else:
            first = self._lines[sr][:sc]
            last = self._lines[er][ec:]
            self._lines[sr] = first + last
            del self._lines[sr + 1:er + 1]
        self._cursor_row = sr
        self._cursor_col = sc
        self._sel_anchor = None
        self._highlight_dirty = True
        self.dirty = True
        return True

    # ── Undo / Redo ───────────────────────────────────────────────────

    def _save_undo(self) -> None:
        """Snapshot current state onto the undo stack."""
        self._undo_stack.append(
            (list(self._lines), self._cursor_row, self._cursor_col)
        )
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _undo(self) -> None:
        if not self._undo_stack:
            return
        # Push current state onto redo stack
        self._redo_stack.append(
            (list(self._lines), self._cursor_row, self._cursor_col)
        )
        lines, row, col = self._undo_stack.pop()
        self._lines = lines
        self._cursor_row = row
        self._cursor_col = col
        self._sel_anchor = None
        self._highlight_dirty = True
        self.dirty = True

    def _redo(self) -> None:
        if not self._redo_stack:
            return
        # Push current state onto undo stack (no clear of redo)
        self._undo_stack.append(
            (list(self._lines), self._cursor_row, self._cursor_col)
        )
        lines, row, col = self._redo_stack.pop()
        self._lines = lines
        self._cursor_row = row
        self._cursor_col = col
        self._sel_anchor = None
        self._highlight_dirty = True
        self.dirty = True

    # ── Highlighting ──────────────────────────────────────────────────

    def _rehighlight(self) -> None:
        """Re-lex the entire text and cache per-line token lists."""
        if not self._highlight_dirty:
            return
        self._highlight_dirty = False

        full_text = "\n".join(self._lines)
        tokens = list(lex(full_text, self._lexer))

        # Split tokens at newline boundaries into per-line lists
        self._highlighted = []
        current_line: list[tuple[str, str]] = []

        for token_type, value in tokens:
            color = _get_color(token_type)
            parts = value.split("\n")
            for i, part in enumerate(parts):
                if i > 0:
                    self._highlighted.append(current_line)
                    current_line = []
                if part:
                    current_line.append((color, part))

        self._highlighted.append(current_line)

        # Pad to match _lines count
        while len(self._highlighted) < len(self._lines):
            self._highlighted.append([])

    # ── Rendering ─────────────────────────────────────────────────────

    def render(self, x: int, y: int, width: int, height: int) -> None:
        """Render the editor within the given rectangle."""
        t = self.term
        self._rehighlight()

        self._gutter_width = max(4, len(str(len(self._lines))) + 2)
        code_width = width - self._gutter_width

        # Ensure cursor is visible
        if self._cursor_row < self._scroll_row:
            self._scroll_row = self._cursor_row
        elif self._cursor_row >= self._scroll_row + height:
            self._scroll_row = self._cursor_row - height + 1

        if self._cursor_col < self._scroll_col:
            self._scroll_col = self._cursor_col
        elif self._cursor_col >= self._scroll_col + code_width:
            self._scroll_col = self._cursor_col - code_width + 1

        for i in range(height):
            line_idx = self._scroll_row + i
            row_y = y + i

            if line_idx >= len(self._lines):
                # Empty line below content
                sys.stdout.write(
                    t.move_xy(x, row_y)
                    + fmt(t, "dim", " " * self._gutter_width)
                    + " " * code_width
                )
                continue

            # Gutter (line number)
            line_num = str(line_idx + 1).rjust(self._gutter_width - 1) + " "
            if line_idx == self._cursor_row:
                gutter = fmt(t, "bold", line_num)
            else:
                gutter = fmt(t, "dim", line_num)

            sys.stdout.write(t.move_xy(x, row_y) + gutter)

            # Code content with syntax highlighting
            if line_idx < len(self._highlighted):
                tokens = self._highlighted[line_idx]
            else:
                tokens = []

            # Build the visible portion of the line
            col = 0
            output_col = 0
            for color, text in tokens:
                for ch in text:
                    if col >= self._scroll_col and output_col < code_width:
                        is_cursor = (
                            line_idx == self._cursor_row
                            and col == self._cursor_col
                        )
                        in_sel = self._in_selection(line_idx, col)
                        if is_cursor:
                            sys.stdout.write(fmt(t, "reverse", ch))
                        elif in_sel:
                            sys.stdout.write(fmt(t, "reverse", ch))
                        elif color:
                            sys.stdout.write(fmt(t, color, ch))
                        else:
                            sys.stdout.write(ch)
                        output_col += 1
                    col += 1

            # Draw cursor if it's past end of line content
            if (
                line_idx == self._cursor_row
                and self._cursor_col >= col
                and self._cursor_col - self._scroll_col < code_width
            ):
                padding = self._cursor_col - col
                if padding > 0 and output_col < code_width:
                    spaces = min(padding, code_width - output_col)
                    sys.stdout.write(" " * spaces)
                    output_col += spaces
                if output_col < code_width:
                    sys.stdout.write(fmt(t, "reverse", " "))
                    output_col += 1

            # Clear rest of line - highlight trailing space if in selection
            remaining = code_width - output_col
            if remaining > 0:
                line_len = len(self._lines[line_idx]) if line_idx < len(self._lines) else 0
                if self._in_selection(line_idx, line_len):
                    sys.stdout.write(fmt(t, "reverse", " " * remaining))
                else:
                    sys.stdout.write(" " * remaining)

        self.dirty = False

    # ── Editing operations ────────────────────────────────────────────

    def handle_key(self, key) -> bool:
        """Process a keystroke. Returns True if the key was consumed."""
        name = getattr(key, "name", None)

        # ── Selection movement (Shift+arrows) ────────────────────────
        if name in ("kUP2", "kDN2", "kLFT2", "kRIT2",
                     "kLFT6", "kRIT6", "kUP6", "kDN6",
                     "kHOM2", "kEND2"):
            if self._sel_anchor is None:
                self._sel_anchor = (self._cursor_row, self._cursor_col)
            if name in ("kUP2", "kUP6"):
                self._move_up()
            elif name in ("kDN2", "kDN6"):
                self._move_down()
            elif name == "kLFT2":
                self._move_left()
            elif name == "kRIT2":
                self._move_right()
            elif name == "kLFT6":
                self._move_word_left()
            elif name == "kRIT6":
                self._move_word_right()
            elif name == "kHOM2":
                self._cursor_col = 0
                self.dirty = True
            elif name == "kEND2":
                self._cursor_col = len(self._lines[self._cursor_row])
                self.dirty = True
            return True

        # ── Word movement (Ctrl+Left/Right) ──────────────────────────
        if name == "kLFT5":
            self._sel_anchor = None
            self._move_word_left()
            return True
        if name == "kRIT5":
            self._sel_anchor = None
            self._move_word_right()
            return True

        # ── Regular cursor movement (clears selection) ───────────────
        if name == "KEY_UP":
            self._sel_anchor = None
            self._move_up()
            return True
        if name == "KEY_DOWN":
            self._sel_anchor = None
            self._move_down()
            return True
        if name == "KEY_LEFT":
            if self._sel_anchor is not None:
                sel = self._sel_range()
                if sel:
                    self._cursor_row, self._cursor_col = sel[0]
                self._sel_anchor = None
                self.dirty = True
                return True
            self._move_left()
            return True
        if name == "KEY_RIGHT":
            if self._sel_anchor is not None:
                sel = self._sel_range()
                if sel:
                    self._cursor_row, self._cursor_col = sel[1]
                self._sel_anchor = None
                self.dirty = True
                return True
            self._move_right()
            return True
        if name == "KEY_HOME":
            self._sel_anchor = None
            self._cursor_col = 0
            self.dirty = True
            return True
        if name == "KEY_END":
            self._sel_anchor = None
            self._cursor_col = len(self._lines[self._cursor_row])
            self.dirty = True
            return True
        if name == "KEY_PGUP":
            self._sel_anchor = None
            self._page_up()
            return True
        if name == "KEY_PGDOWN":
            self._sel_anchor = None
            self._page_down()
            return True

        # ── Undo / Redo ──────────────────────────────────────────────
        # Ctrl+U for undo (also Ctrl+Z as fallback)
        if key == "\x15" or key == "\x1a":
            self._undo()
            return True
        # Ctrl+R for redo (also Ctrl+Y as fallback)
        if key == "\x12" or key == "\x19":
            self._redo()
            return True

        # ── Editing (replaces selection if active) ───────────────────
        if name == "KEY_BACKSPACE":
            if self._delete_selection():
                return True
            self._save_undo()
            self._backspace()
            return True
        if name == "KEY_DELETE":
            if self._delete_selection():
                return True
            self._save_undo()
            self._delete()
            return True
        if name == "KEY_ENTER":
            self._save_undo()
            self._delete_selection()
            self._enter()
            return True
        if name == "KEY_TAB" or key == "\t":
            self._save_undo()
            self._delete_selection()
            self._insert_text("    ")
            return True

        # ── Character insertion ──────────────────────────────────────
        if key and not getattr(key, "is_sequence", False):
            self._save_undo()
            self._delete_selection()
            self._insert_char(key)
            return True

        return False

    def _insert_char(self, ch: str) -> None:
        line = self._lines[self._cursor_row]
        self._lines[self._cursor_row] = (
            line[: self._cursor_col] + ch + line[self._cursor_col :]
        )
        self._cursor_col += len(ch)
        self._highlight_dirty = True
        self.dirty = True

    def _insert_text(self, text: str) -> None:
        line = self._lines[self._cursor_row]
        self._lines[self._cursor_row] = (
            line[: self._cursor_col] + text + line[self._cursor_col :]
        )
        self._cursor_col += len(text)
        self._highlight_dirty = True
        self.dirty = True

    def _backspace(self) -> None:
        if self._cursor_col > 0:
            line = self._lines[self._cursor_row]
            self._lines[self._cursor_row] = (
                line[: self._cursor_col - 1] + line[self._cursor_col :]
            )
            self._cursor_col -= 1
        elif self._cursor_row > 0:
            # Merge with previous line
            prev_len = len(self._lines[self._cursor_row - 1])
            self._lines[self._cursor_row - 1] += self._lines[self._cursor_row]
            self._lines.pop(self._cursor_row)
            self._cursor_row -= 1
            self._cursor_col = prev_len
        else:
            return
        self._highlight_dirty = True
        self.dirty = True

    def _delete(self) -> None:
        line = self._lines[self._cursor_row]
        if self._cursor_col < len(line):
            self._lines[self._cursor_row] = (
                line[: self._cursor_col] + line[self._cursor_col + 1 :]
            )
        elif self._cursor_row < len(self._lines) - 1:
            self._lines[self._cursor_row] += self._lines[self._cursor_row + 1]
            self._lines.pop(self._cursor_row + 1)
        else:
            return
        self._highlight_dirty = True
        self.dirty = True

    def _enter(self) -> None:
        line = self._lines[self._cursor_row]
        # Auto-indent: copy leading whitespace from current line
        indent = ""
        for ch in line:
            if ch in (" ", "\t"):
                indent += ch
            else:
                break
        before = line[: self._cursor_col]
        after = line[self._cursor_col :]
        self._lines[self._cursor_row] = before
        self._lines.insert(self._cursor_row + 1, indent + after)
        self._cursor_row += 1
        self._cursor_col = len(indent)
        self._highlight_dirty = True
        self.dirty = True

    def _move_up(self) -> None:
        if self._cursor_row > 0:
            self._cursor_row -= 1
            self._cursor_col = min(self._cursor_col, len(self._lines[self._cursor_row]))
            self.dirty = True

    def _move_down(self) -> None:
        if self._cursor_row < len(self._lines) - 1:
            self._cursor_row += 1
            self._cursor_col = min(self._cursor_col, len(self._lines[self._cursor_row]))
            self.dirty = True

    def _move_left(self) -> None:
        if self._cursor_col > 0:
            self._cursor_col -= 1
            self.dirty = True
        elif self._cursor_row > 0:
            self._cursor_row -= 1
            self._cursor_col = len(self._lines[self._cursor_row])
            self.dirty = True

    def _move_right(self) -> None:
        line = self._lines[self._cursor_row]
        if self._cursor_col < len(line):
            self._cursor_col += 1
            self.dirty = True
        elif self._cursor_row < len(self._lines) - 1:
            self._cursor_row += 1
            self._cursor_col = 0
            self.dirty = True

    def _move_word_left(self) -> None:
        if self._cursor_col > 0:
            line = self._lines[self._cursor_row]
            col = self._cursor_col - 1
            # Skip non-word chars
            while col > 0 and not (line[col].isalnum() or line[col] == "_"):
                col -= 1
            # Skip word chars
            while col > 0 and (line[col - 1].isalnum() or line[col - 1] == "_"):
                col -= 1
            self._cursor_col = col
        elif self._cursor_row > 0:
            self._cursor_row -= 1
            self._cursor_col = len(self._lines[self._cursor_row])
        self.dirty = True

    def _move_word_right(self) -> None:
        line = self._lines[self._cursor_row]
        if self._cursor_col < len(line):
            col = self._cursor_col
            # Skip word chars
            while col < len(line) and (line[col].isalnum() or line[col] == "_"):
                col += 1
            # Skip non-word chars
            while col < len(line) and not (line[col].isalnum() or line[col] == "_"):
                col += 1
            self._cursor_col = col
        elif self._cursor_row < len(self._lines) - 1:
            self._cursor_row += 1
            self._cursor_col = 0
        self.dirty = True

    def _page_up(self) -> None:
        self._cursor_row = max(0, self._cursor_row - 20)
        self._cursor_col = min(self._cursor_col, len(self._lines[self._cursor_row]))
        self.dirty = True

    def _page_down(self) -> None:
        self._cursor_row = min(len(self._lines) - 1, self._cursor_row + 20)
        self._cursor_col = min(self._cursor_col, len(self._lines[self._cursor_row]))
        self.dirty = True
