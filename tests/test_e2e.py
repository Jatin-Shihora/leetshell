"""End-to-end test: open multiple problems at multiple terminal sizes."""

import asyncio
import io
import re
import sys
import time

ANSI = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
MOVE = re.compile(r'\x1b\[(\d+);(\d+)H')

PASS = 0
FAIL = 0


class TT:
    """Test terminal with configurable size and safe formatting."""

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

    def bold(self, t):
        return self._w2(1, t)

    def dim(self, t):
        return self._w2(2, t)

    def reverse(self, t):
        return self._w2(7, t)

    def green(self, t):
        return self._w2(32, t)

    def yellow(self, t):
        return self._w2(33, t)

    def red(self, t):
        return self._w2(31, t)

    def cyan(self, t):
        return self._w2(36, t)

    def magenta(self, t):
        return self._w2(35, t)

    def blue(self, t):
        return self._w2(34, t)

    def white(self, t):
        return self._w2(37, t)

    def bright_black(self, t):
        return self._w2(90, t)

    def bright_green(self, t):
        return self._w2(92, t)

    def bright_red(self, t):
        return self._w2(91, t)

    def bright_cyan(self, t):
        return self._w2(96, t)

    def length(self, t):
        return len(ANSI.sub("", t))


def strip(t):
    return ANSI.sub("", t)


def parse_rows(buf):
    rows = {}
    segments = []
    pos = 0
    for m in MOVE.finditer(buf):
        if pos < m.start():
            segments.append(("t", buf[pos : m.start()]))
        segments.append(("m", int(m.group(1)) - 1, int(m.group(2)) - 1))
        pos = m.end()
    if pos < len(buf):
        segments.append(("t", buf[pos:]))
    cr, cc = 0, 0
    for s in segments:
        if s[0] == "m":
            cr, cc = s[1], s[2]
        else:
            t = strip(s[1])
            if t:
                rows.setdefault(cr, []).append((cc, t))
    return rows


def row_text(rows, r):
    if r not in rows:
        return ""
    return "".join(t for _, t in rows[r])


def all_text(rows):
    return "".join(row_text(rows, r) for r in sorted(rows))


def check(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"    [PASS] {label}")
    else:
        FAIL += 1
        print(f"    [FAIL] {label} -- {detail}")


def capture(fn):
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        fn()
    finally:
        sys.stdout = old
    return buf.getvalue()


async def main():
    from leetshell.app import LeetCodeApp
    from leetshell.tui.problem_detail import ProblemDetailScreen

    sizes = [(120, 40), (80, 25), (160, 50)]

    problems = [
        ("two-sum", "Easy", "Two Sum"),
        ("add-two-numbers", "Medium", "Add Two Numbers"),
        ("longest-substring-without-repeating-characters", "Medium", "Longest Substring"),
        ("median-of-two-sorted-arrays", "Hard", "Median of Two"),
        ("reverse-integer", "Medium", "Reverse Integer"),
    ]

    for w, h in sizes:
        print(f"\n{'=' * 70}")
        print(f"  TERMINAL SIZE: {w}x{h}")
        print(f"{'=' * 70}")

        term = TT(w, h)
        app = LeetCodeApp()
        app.term = term
        await app._startup()
        await asyncio.sleep(2)

        # ── Problem list ──
        screen = app.current_screen
        if screen:
            screen.term = term
            await asyncio.sleep(1)

            rendered = capture(screen.render)
            rows = parse_rows(rendered)

            print(f"\n  --- Problem List ({w}x{h}) ---")
            check("Filter bar has Difficulty", "Difficulty" in row_text(rows, 0))
            r1 = row_text(rows, 1)
            check("Header has # Title Diff AC%",
                  "#" in r1 and "Title" in r1 and "Difficulty" in r1 and "AC%" in r1)
            check("Data rows exist",
                  any(row_text(rows, r).strip() for r in range(2, min(h - 2, 10))))
            check("Status bar has pg", "pg" in row_text(rows, h - 1))

        # ── Each problem ──
        for slug, diff, title in problems:
            print(f"\n  --- {title} @ {w}x{h} ---")

            detail = ProblemDetailScreen(app, slug)
            detail.term = term
            await app.push_screen(detail)
            await asyncio.sleep(3)

            check("Detail loaded", detail._detail is not None)
            if not detail._detail:
                await app.pop_screen()
                continue

            check("Editor created", detail._editor is not None)
            check("Desc lines > 0", len(detail._desc_lines) > 0,
                  f"{len(detail._desc_lines)} lines")

            # No ** markers
            has_bold = any("**" in l for l in detail._desc_lines)
            check("No ** markers", not has_bold)

            # Lines wrapped to width
            long = [i for i, l in enumerate(detail._desc_lines) if len(l) > w]
            check("Desc lines fit width", len(long) == 0,
                  f"{len(long)} lines > {w} chars")

            # No consecutive blank lines
            consec = 0
            max_consec = 0
            for l in detail._desc_lines:
                if not l.strip():
                    consec += 1
                    max_consec = max(max_consec, consec)
                else:
                    consec = 0
            check("No excessive blanks", max_consec <= 2, f"max={max_consec}")

            if detail._editor:
                detail._editor.term = term

            # ── Split view (default) ──
            rendered = capture(detail.render)
            rows = parse_rows(rendered)
            full = all_text(rows)

            # Header
            check("Header has title", title[:8] in row_text(rows, 0),
                  f"row0={row_text(rows, 0)[:40]}")
            check("Meta has difficulty", diff in row_text(rows, 1))
            check("Divider has dashes", row_text(rows, 2).count("-") > 10)

            # Split view: divider and lang header
            check("Split view: divider", "│" in full)
            check("Split view: lang header", "---" in full)

            # Status bar mentions editor or scroll
            r_last = row_text(rows, h - 1)
            check("Split status bar",
                  "editor" in r_last.lower() or "scroll" in r_last.lower(),
                  f"last row: {r_last[:50]}")

            # ── Description view (Ctrl+D: split → editor → desc) ──
            detail._view_mode = "desc"
            detail.dirty = True
            if detail._editor:
                detail._editor.term = term
            try:
                rendered_d = capture(detail.render)
                rows_d = parse_rows(rendered_d)
                full_d = all_text(rows_d)
                check("Example 1 visible", "Example 1" in full_d)
                r_last_d = row_text(rows_d, h - 1)
                check("Desc status bar",
                      "split" in r_last_d.lower() or "esc" in r_last_d.lower(),
                      f"last row: {r_last_d[:50]}")
            except Exception as e:
                check("Desc view render OK", False, str(e))

            # ── Editor view ──
            detail._view_mode = "editor"
            detail.dirty = True
            if detail._editor:
                detail._editor.term = term
            try:
                rendered2 = capture(detail.render)
                rows2 = parse_rows(rendered2)
                full2 = all_text(rows2)
                # Editor header visible
                check("Editor view: header ---", "---" in full2)
                # Line numbers visible
                has_lnum = any(
                    re.search(r"\d+\s", row_text(rows2, r)[:8])
                    for r in range(4, h - 2)
                    if r in rows2
                )
                check("Editor view: line numbers", has_lnum)
                # Status bar shows ^p description hint
                r_last2 = row_text(rows2, h - 1)
                check("Editor status bar",
                      "description" in r_last2.lower() or "test" in r_last2.lower(),
                      f"last row: {r_last2[:50]}")
            except Exception as e:
                check("Editor view render OK", False, str(e))

            # Language cycling (in editor view)
            old_lang = detail._lang_slug
            detail._action_next_lang()
            if detail._editor:
                detail._editor.term = term
            new_lang = detail._lang_slug
            check("Language cycle works", new_lang != old_lang,
                  f"{old_lang} -> {new_lang}")

            # Render after lang change (no crash)
            try:
                capture(detail.render)
                check("Render after lang OK", True)
            except Exception as e:
                check("Render after lang OK", False, str(e))

            # Editor insert + render (no crash)
            if detail._editor:
                detail._editor._insert_char("x")
                detail._editor._highlight_dirty = True
                try:
                    capture(detail.render)
                    check("Edit + render OK", True)
                except Exception as e:
                    check("Edit + render OK", False, str(e))
                detail._editor._backspace()
                detail._editor._highlight_dirty = True

            detail._view_mode = "split"

            await app.pop_screen()

        await app.client.close()

    print(f"\n{'=' * 70}")
    print(f"  TOTAL: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 70}")
    if FAIL > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
