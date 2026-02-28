"""Manual key handling verification across all 3 view modes.

Simulates arrow keys, Shift+arrows, Ctrl+arrows, typing, and selection
in split/editor/desc views to verify correct behavior.
"""

import asyncio
import io
import re
import sys

ANSI = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')


class Key(str):
    """Simulate blessed Keystroke (str subclass with .name and .is_sequence)."""
    def __new__(cls, name=None, ch=None, is_sequence=True):
        obj = str.__new__(cls, ch or "")
        obj.name = name
        obj.is_sequence = is_sequence
        return obj


class TT:
    def __init__(self, w=120, h=40):
        self._w, self._h = w, h

    @property
    def width(self):
        return self._w

    @property
    def height(self):
        return self._h

    @property
    def is_a_tty(self):
        return True

    @property
    def number_of_colors(self):
        return 256

    def move_xy(self, x, y):
        return f"\x1b[{y + 1};{x + 1}H"

    @property
    def clear(self):
        return "\x1b[2J"

    @property
    def clear_eol(self):
        return "\x1b[K"

    def _w2(self, c, t):
        return f"\x1b[{c}m{t}\x1b[0m"

    def bold(self, t): return self._w2(1, t)
    def dim(self, t): return self._w2(2, t)
    def reverse(self, t): return self._w2(7, t)
    def green(self, t): return self._w2(32, t)
    def yellow(self, t): return self._w2(33, t)
    def red(self, t): return self._w2(31, t)
    def cyan(self, t): return self._w2(36, t)
    def magenta(self, t): return self._w2(35, t)
    def blue(self, t): return self._w2(34, t)
    def white(self, t): return self._w2(37, t)
    def bright_black(self, t): return self._w2(90, t)
    def bright_green(self, t): return self._w2(92, t)
    def bright_red(self, t): return self._w2(91, t)
    def bright_cyan(self, t): return self._w2(96, t)
    def length(self, t): return len(ANSI.sub("", t))


PASS = 0
FAIL = 0


def check(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label} -- {detail}")


async def main():
    from leetshell.app import LeetCodeApp
    from leetshell.tui.problem_detail import ProblemDetailScreen

    term = TT(120, 40)
    app = LeetCodeApp()
    app.term = term
    await app._startup()
    await asyncio.sleep(2)

    detail = ProblemDetailScreen(app, "two-sum")
    detail.term = term
    await app.push_screen(detail)
    await asyncio.sleep(3)

    ed = detail._editor
    ed.term = term

    print("=" * 60)
    print("  SPLIT VIEW: Arrow keys move editor cursor")
    print("=" * 60)
    detail._view_mode = "split"
    ed._cursor_row = 0
    ed._cursor_col = 0
    ed._sel_anchor = None

    check("Initial cursor at (0,0)",
          ed._cursor_row == 0 and ed._cursor_col == 0,
          f"({ed._cursor_row},{ed._cursor_col})")

    # Arrow Down → cursor moves, desc does NOT scroll
    old_scroll = detail._desc_scroll
    await detail.handle_key(Key(name="KEY_DOWN"))
    check("Arrow Down: cursor row=1", ed._cursor_row == 1,
          f"row={ed._cursor_row}")
    check("Arrow Down: desc scroll unchanged", detail._desc_scroll == old_scroll,
          f"scroll={detail._desc_scroll}")

    # Arrow Up → cursor moves back
    await detail.handle_key(Key(name="KEY_UP"))
    check("Arrow Up: cursor row=0", ed._cursor_row == 0,
          f"row={ed._cursor_row}")

    # Arrow Right x3
    await detail.handle_key(Key(name="KEY_RIGHT"))
    await detail.handle_key(Key(name="KEY_RIGHT"))
    await detail.handle_key(Key(name="KEY_RIGHT"))
    check("Arrow Right x3: col=3", ed._cursor_col == 3,
          f"col={ed._cursor_col}")

    # Arrow Left
    await detail.handle_key(Key(name="KEY_LEFT"))
    check("Arrow Left: col=2", ed._cursor_col == 2,
          f"col={ed._cursor_col}")

    print()
    print("=" * 60)
    print("  SPLIT VIEW: Ctrl+Up/Down scroll description")
    print("=" * 60)
    detail._desc_scroll = 0
    old_row = ed._cursor_row
    old_col = ed._cursor_col

    await detail.handle_key(Key(name="kDN5"))
    check("Ctrl+Down: desc scroll=1", detail._desc_scroll == 1,
          f"scroll={detail._desc_scroll}")
    check("Ctrl+Down: cursor unchanged",
          ed._cursor_row == old_row and ed._cursor_col == old_col,
          f"({ed._cursor_row},{ed._cursor_col})")

    await detail.handle_key(Key(name="kUP5"))
    check("Ctrl+Up: desc scroll=0", detail._desc_scroll == 0,
          f"scroll={detail._desc_scroll}")

    print()
    print("=" * 60)
    print("  SPLIT VIEW: Ctrl+Left/Right word movement")
    print("=" * 60)
    ed._cursor_row = 0
    ed._cursor_col = 0
    ed._sel_anchor = None

    await detail.handle_key(Key(name="kRIT5"))  # Ctrl+Right
    check("Ctrl+Right: col > 0", ed._cursor_col > 0,
          f"col={ed._cursor_col}, line[0]={ed._lines[0][:30]}...")
    word_end = ed._cursor_col

    await detail.handle_key(Key(name="kLFT5"))  # Ctrl+Left
    check("Ctrl+Left: col < word_end", ed._cursor_col < word_end,
          f"col={ed._cursor_col}")

    print()
    print("=" * 60)
    print("  SPLIT VIEW: Shift+Right character selection")
    print("=" * 60)
    ed._cursor_row = 0
    ed._cursor_col = 0
    ed._sel_anchor = None

    await detail.handle_key(Key(name="kRIT2"))
    await detail.handle_key(Key(name="kRIT2"))
    await detail.handle_key(Key(name="kRIT2"))
    check("Shift+Right x3: anchor set", ed._sel_anchor is not None,
          f"anchor={ed._sel_anchor}")
    check("Shift+Right x3: cursor col=3", ed._cursor_col == 3,
          f"col={ed._cursor_col}")
    sel = ed._sel_range()
    check("Selection: (0,0)-(0,3)", sel == ((0, 0), (0, 3)),
          f"sel={sel}")
    check("Col 0 in selection", ed._in_selection(0, 0))
    check("Col 2 in selection", ed._in_selection(0, 2))
    check("Col 3 NOT in selection", not ed._in_selection(0, 3))

    # Plain Left → jump to start of selection, clear
    await detail.handle_key(Key(name="KEY_LEFT"))
    check("Left clears selection", ed._sel_anchor is None)
    check("Cursor at selection start (col=0)", ed._cursor_col == 0,
          f"col={ed._cursor_col}")

    print()
    print("=" * 60)
    print("  SPLIT VIEW: Shift+Down multi-line selection")
    print("=" * 60)
    ed._cursor_row = 0
    ed._cursor_col = 0
    ed._sel_anchor = None

    await detail.handle_key(Key(name="kDN2"))  # Shift+Down
    check("Shift+Down: anchor=(0,0)", ed._sel_anchor == (0, 0),
          f"anchor={ed._sel_anchor}")
    check("Shift+Down: cursor row=1", ed._cursor_row == 1,
          f"row={ed._cursor_row}")

    await detail.handle_key(Key(name="kDN2"))  # Shift+Down again
    check("Shift+Down x2: cursor row=2", ed._cursor_row == 2,
          f"row={ed._cursor_row}")
    check("Row 1 in selection", ed._in_selection(1, 0))

    print()
    print("=" * 60)
    print("  SPLIT VIEW: Type replaces selection")
    print("=" * 60)
    # We have selection from (0,0) to (2, cursor_col)
    old_lines = len(ed._lines)
    await detail.handle_key(Key(ch="x", is_sequence=False))
    check("Typing clears selection", ed._sel_anchor is None)
    check("Lines reduced after replace", len(ed._lines) < old_lines,
          f"{old_lines} -> {len(ed._lines)}")

    # Backspace to undo the 'x'
    await detail.handle_key(Key(name="KEY_BACKSPACE"))

    print()
    print("=" * 60)
    print("  SPLIT VIEW: Ctrl+Shift+Right word selection")
    print("=" * 60)
    ed._cursor_row = 0
    ed._cursor_col = 0
    ed._sel_anchor = None

    await detail.handle_key(Key(name="kRIT6"))  # Ctrl+Shift+Right
    check("Ctrl+Shift+Right: anchor set", ed._sel_anchor is not None,
          f"anchor={ed._sel_anchor}")
    check("Ctrl+Shift+Right: col > 0", ed._cursor_col > 0,
          f"col={ed._cursor_col}")
    sel = ed._sel_range()
    check("Word selection range valid", sel is not None and sel[1][1] > sel[0][1],
          f"sel={sel}")

    # Clear selection
    await detail.handle_key(Key(name="KEY_RIGHT"))

    print()
    print("=" * 60)
    print("  SPLIT VIEW: Backspace with selection deletes selection only")
    print("=" * 60)
    ed._cursor_row = 0
    ed._cursor_col = 0
    ed._sel_anchor = None
    line_before = ed._lines[0]

    # Select 2 chars then backspace
    await detail.handle_key(Key(name="kRIT2"))
    await detail.handle_key(Key(name="kRIT2"))
    await detail.handle_key(Key(name="KEY_BACKSPACE"))
    check("Backspace: selection cleared", ed._sel_anchor is None)
    check("Backspace: 2 chars removed",
          ed._lines[0] == line_before[2:],
          f"expected={line_before[2:][:20]}, got={ed._lines[0][:20]}")

    # Restore
    ed._lines[0] = line_before
    ed._highlight_dirty = True

    print()
    print("=" * 60)
    print("  EDITOR VIEW: Same key tests")
    print("=" * 60)
    detail._view_mode = "editor"
    ed._cursor_row = 0
    ed._cursor_col = 0
    ed._sel_anchor = None

    await detail.handle_key(Key(name="KEY_DOWN"))
    check("Editor: Down moves cursor", ed._cursor_row == 1,
          f"row={ed._cursor_row}")

    await detail.handle_key(Key(name="KEY_UP"))
    check("Editor: Up moves cursor", ed._cursor_row == 0,
          f"row={ed._cursor_row}")

    # Shift+Right
    await detail.handle_key(Key(name="kRIT2"))
    await detail.handle_key(Key(name="kRIT2"))
    check("Editor: Shift+Right selects", ed._sel_anchor is not None)
    check("Editor: cursor at col 2", ed._cursor_col == 2,
          f"col={ed._cursor_col}")
    ed._sel_anchor = None

    # Ctrl+Right
    ed._cursor_col = 0
    await detail.handle_key(Key(name="kRIT5"))
    check("Editor: Ctrl+Right word move", ed._cursor_col > 0,
          f"col={ed._cursor_col}")

    print()
    print("=" * 60)
    print("  DESC VIEW: Arrows scroll description (no editor)")
    print("=" * 60)
    detail._view_mode = "desc"
    detail._desc_scroll = 0

    await detail.handle_key(Key(name="KEY_DOWN"))
    check("Desc: Down scrolls", detail._desc_scroll == 1,
          f"scroll={detail._desc_scroll}")

    await detail.handle_key(Key(name="KEY_UP"))
    check("Desc: Up scrolls back", detail._desc_scroll == 0,
          f"scroll={detail._desc_scroll}")

    print()
    print("=" * 60)
    print("  RENDER: Selection visible in output")
    print("=" * 60)
    detail._view_mode = "editor"
    ed._cursor_row = 0
    ed._cursor_col = 5
    ed._sel_anchor = (0, 0)

    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        detail.render()
    finally:
        sys.stdout = old
    output = buf.getvalue()
    check("Selection renders with reverse escape", "\x1b[7m" in output)

    ed._sel_anchor = None

    await app.client.close()

    print()
    print("=" * 60)
    print(f"  TOTAL: {PASS} passed, {FAIL} failed")
    print("=" * 60)
    if FAIL > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
