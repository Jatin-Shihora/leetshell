"""Comprehensive UI/UX test: renders problems in all 3 view modes at multiple sizes.

Usage: python test_comprehensive.py <batch_number>
  batch_number: 1-5 (each batch tests ~39 problems from cache)
"""

import asyncio
import io
import re
import sys
import time

ANSI = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
MOVE = re.compile(r'\x1b\[(\d+);(\d+)H')

PASS = 0
FAIL = 0

# All 193 cached problem slugs
ALL_SLUGS = [
    "3sum", "3sum-closest", "4sum", "add-binary", "add-two-numbers",
    "balanced-binary-tree", "best-time-to-buy-and-sell-stock",
    "best-time-to-buy-and-sell-stock-ii", "best-time-to-buy-and-sell-stock-iii",
    "best-time-to-buy-and-sell-stock-iv", "binary-search-tree-iterator",
    "binary-tree-inorder-traversal", "binary-tree-level-order-traversal",
    "binary-tree-level-order-traversal-ii", "binary-tree-maximum-path-sum",
    "binary-tree-postorder-traversal", "binary-tree-preorder-traversal",
    "binary-tree-right-side-view", "binary-tree-zigzag-level-order-traversal",
    "candy", "climbing-stairs", "clone-graph", "combinations", "combination-sum",
    "combination-sum-ii", "combine-two-tables", "compare-version-numbers",
    "consecutive-numbers",
    "construct-binary-tree-from-inorder-and-postorder-traversal",
    "construct-binary-tree-from-preorder-and-inorder-traversal",
    "container-with-most-water", "convert-sorted-array-to-binary-search-tree",
    "convert-sorted-list-to-binary-search-tree", "copy-list-with-random-pointer",
    "count-and-say", "count-islands-with-total-value-divisible-by-k",
    "customers-who-never-order", "decode-ways", "delete-duplicate-emails",
    "department-highest-salary", "department-top-three-salaries",
    "distinct-subsequences", "divide-two-integers", "dungeon-game",
    "duplicate-emails", "edit-distance", "employees-earning-more-than-their-managers",
    "evaluate-reverse-polish-notation", "excel-sheet-column-number",
    "excel-sheet-column-title", "factorial-trailing-zeroes",
    "find-first-and-last-position-of-element-in-sorted-array",
    "find-minimum-in-rotated-sorted-array", "find-minimum-in-rotated-sorted-array-ii",
    "find-peak-element", "find-the-index-of-the-first-occurrence-in-a-string",
    "first-missing-positive", "flatten-binary-tree-to-linked-list",
    "fraction-to-recurring-decimal", "gas-station", "generate-parentheses",
    "gray-code", "group-anagrams", "house-robber", "insert-interval",
    "insertion-sort-list", "integer-to-roman", "interleaving-string",
    "intersection-of-two-linked-lists", "island-perimeter", "jump-game",
    "jump-game-ii", "largest-number", "largest-rectangle-in-histogram",
    "length-of-last-word", "letter-combinations-of-a-phone-number",
    "linked-list-cycle", "linked-list-cycle-ii", "longest-common-prefix",
    "longest-consecutive-sequence", "longest-palindromic-substring",
    "longest-substring-without-repeating-characters", "longest-valid-parentheses",
    "lru-cache", "majority-element", "maximal-rectangle",
    "maximum-depth-of-binary-tree", "maximum-gap", "maximum-product-subarray",
    "maximum-subarray", "max-points-on-a-line", "median-of-two-sorted-arrays",
    "merge-intervals", "merge-k-sorted-lists", "merge-sorted-array",
    "merge-two-sorted-lists", "minimum-depth-of-binary-tree", "minimum-path-sum",
    "minimum-window-substring", "min-stack", "multiply-strings",
    "next-permutation", "n-queens", "n-queens-ii", "nth-highest-salary",
    "number-of-1-bits", "palindrome-number", "palindrome-partitioning",
    "palindrome-partitioning-ii", "partition-list", "pascals-triangle",
    "pascals-triangle-ii", "path-sum", "path-sum-ii", "permutations",
    "permutation-sequence", "permutations-ii", "plus-one",
    "populating-next-right-pointers-in-each-node",
    "populating-next-right-pointers-in-each-node-ii", "powx-n", "rank-scores",
    "recover-binary-search-tree", "regular-expression-matching",
    "remove-duplicates-from-sorted-array", "remove-duplicates-from-sorted-array-ii",
    "remove-duplicates-from-sorted-list", "remove-duplicates-from-sorted-list-ii",
    "remove-element", "remove-nth-node-from-end-of-list", "reorder-list",
    "repeated-dna-sequences", "restore-ip-addresses", "reverse-bits",
    "reverse-integer", "reverse-linked-list-ii", "reverse-nodes-in-k-group",
    "reverse-words-in-a-string", "rising-temperature", "roman-to-integer",
    "rotate-array", "rotate-image", "rotate-list", "same-tree", "scramble-string",
    "search-a-2d-matrix", "search-in-rotated-sorted-array",
    "search-in-rotated-sorted-array-ii", "search-insert-position",
    "second-highest-salary", "set-matrix-zeroes", "simplify-path", "single-number",
    "single-number-ii", "sort-colors", "sort-list", "spiral-matrix",
    "spiral-matrix-ii", "sqrtx", "string-to-integer-atoi", "subsets", "subsets-ii",
    "substring-with-concatenation-of-all-words", "sudoku-solver",
    "sum-root-to-leaf-numbers", "surrounded-regions", "swap-nodes-in-pairs",
    "symmetric-tree", "tenth-line", "text-justification", "transpose-file",
    "trapping-rain-water", "triangle", "two-sum", "two-sum-ii-input-array-is-sorted",
    "unique-binary-search-trees", "unique-binary-search-trees-ii", "unique-paths",
    "unique-paths-ii", "validate-binary-search-tree", "valid-number",
    "valid-palindrome", "valid-parentheses", "valid-phone-numbers", "valid-sudoku",
    "wildcard-matching", "word-break", "word-break-ii", "word-frequency",
    "word-ladder", "word-ladder-ii", "word-search", "zigzag-conversion",
]

# SQL-only problems that have no code snippets (only SQL editors)
SQL_PROBLEMS = {
    "combine-two-tables", "consecutive-numbers", "customers-who-never-order",
    "delete-duplicate-emails", "department-highest-salary",
    "department-top-three-salaries", "duplicate-emails",
    "employees-earning-more-than-their-managers", "nth-highest-salary",
    "rank-scores", "rising-temperature", "second-highest-salary",
}

# Shell-only problems
SHELL_PROBLEMS = {
    "tenth-line", "transpose-file", "valid-phone-numbers", "word-frequency",
}


class TT:
    """Test terminal with configurable size."""
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


def strip(t):
    return ANSI.sub("", t)


def parse_rows(buf):
    rows = {}
    segments = []
    pos = 0
    for m in MOVE.finditer(buf):
        if pos < m.start():
            segments.append(("t", buf[pos:m.start()]))
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


async def test_problem(app, slug, term, w, h):
    """Test a single problem across all 3 view modes."""
    from leetshell.tui.problem_detail import ProblemDetailScreen, _rewrap_lines

    detail = ProblemDetailScreen(app, slug)
    detail.term = term
    await app.push_screen(detail)
    await asyncio.sleep(3)

    prefix = f"[{slug}@{w}x{h}]"

    if not detail._detail:
        check(f"{prefix} Detail loaded", False, "timeout or error")
        await app.pop_screen()
        return

    check(f"{prefix} Detail loaded", True)

    is_sql = slug in SQL_PROBLEMS
    is_shell = slug in SHELL_PROBLEMS

    # -- Data integrity checks --
    if not is_sql and not is_shell:
        check(f"{prefix} Editor created", detail._editor is not None)
    check(f"{prefix} Desc lines > 0", len(detail._desc_lines) > 0)
    check(f"{prefix} Raw desc lines > 0", len(detail._desc_lines_raw) > 0)

    # No ** bold markers
    has_bold = any("**" in l for l in detail._desc_lines)
    check(f"{prefix} No ** markers", not has_bold)

    # No excessive consecutive blank lines
    consec = 0
    max_consec = 0
    for l in detail._desc_lines:
        if not l.strip():
            consec += 1
            max_consec = max(max_consec, consec)
        else:
            consec = 0
    check(f"{prefix} No excessive blanks", max_consec <= 2, f"max={max_consec}")

    if detail._editor:
        detail._editor.term = term

    # ========== SPLIT VIEW (default) ==========
    detail._view_mode = "split"
    detail._desc_scroll = 0
    try:
        rendered = capture(detail.render)
        rows = parse_rows(rendered)
        full = all_text(rows)

        # Header row has problem title
        row0 = row_text(rows, 0)
        check(f"{prefix} Split: header has title",
              detail._detail.title[:6] in row0 or str(detail._detail.frontend_id) in row0,
              f"row0={row0[:50]}")

        # Difficulty in meta row
        check(f"{prefix} Split: meta has difficulty",
              detail._detail.difficulty in row_text(rows, 1))

        # Divider row (row 2)
        check(f"{prefix} Split: divider row", row_text(rows, 2).count("-") > 10)

        # Vertical divider │ present in content area
        check(f"{prefix} Split: vert divider │", "│" in full)

        # Language header --- visible on the right pane
        check(f"{prefix} Split: lang header ---", "---" in full)

        # Status bar mentions "editor" and "scroll"
        status = row_text(rows, h - 1).lower()
        check(f"{prefix} Split: status bar has ^d",
              "^d" in status or "editor" in status,
              f"status={status[:60]}")

        # Description text wraps properly for split width (no truncation beyond pane)
        desc_w = w * 2 // 5
        desc_text_w = max(10, desc_w - 2)
        split_desc = _rewrap_lines(detail._desc_lines_raw, desc_text_w)
        # All wrapped lines should fit
        overlong = [l for l in split_desc if len(l) > desc_text_w]
        check(f"{prefix} Split: desc lines fit pane",
              len(overlong) == 0,
              f"{len(overlong)} lines > {desc_text_w}")

        # Content rows should not bleed past desc_w
        for r in range(3, min(h - 1, 10)):
            rt = row_text(rows, r)
            # The row includes both panes, check divider is present
            if "│" in rt:
                parts = rt.split("│", 1)
                # Left part should not be excessively long
                check(f"{prefix} Split: row {r} left pane bounded",
                      len(parts[0]) <= desc_w + 2,  # small tolerance
                      f"left={len(parts[0])}, desc_w={desc_w}")
                break  # just check one content row

    except Exception as e:
        check(f"{prefix} Split: render OK", False, str(e))

    # ========== DESCRIPTION VIEW ==========
    detail._view_mode = "desc"
    detail._desc_scroll = 0
    try:
        rendered = capture(detail.render)
        rows = parse_rows(rendered)
        full = all_text(rows)

        # Description lines should fit terminal width
        long_lines = [i for i, l in enumerate(detail._desc_lines) if len(l) > w]
        check(f"{prefix} Desc: lines fit width",
              len(long_lines) == 0,
              f"{len(long_lines)} lines > {w}")

        # Status bar mentions "split"
        status = row_text(rows, h - 1).lower()
        check(f"{prefix} Desc: status mentions split",
              "split" in status or "esc" in status,
              f"status={status[:60]}")

    except Exception as e:
        check(f"{prefix} Desc: render OK", False, str(e))

    # ========== EDITOR VIEW ==========
    if not is_sql and not is_shell:
        detail._view_mode = "editor"
        try:
            rendered = capture(detail.render)
            rows = parse_rows(rendered)
            full = all_text(rows)

            # Editor header --- visible
            check(f"{prefix} Editor: header ---", "---" in full)

            # Line numbers visible
            has_lnum = any(
                re.search(r"\d+\s", row_text(rows, r)[:8])
                for r in range(4, h - 2) if r in rows
            )
            check(f"{prefix} Editor: line numbers", has_lnum)

            # Status bar mentions "description"
            status = row_text(rows, h - 1).lower()
            check(f"{prefix} Editor: status mentions desc",
                  "description" in status or "test" in status,
                  f"status={status[:60]}")

        except Exception as e:
            check(f"{prefix} Editor: render OK", False, str(e))

    # ========== MODE CYCLING ==========
    # Verify the cycle works without crash
    for mode in ["split", "editor", "desc", "split"]:
        detail._view_mode = mode
        try:
            capture(detail.render)
        except Exception as e:
            check(f"{prefix} Cycle to {mode} OK", False, str(e))

    detail._view_mode = "split"
    await app.pop_screen()


async def main():
    batch = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    assert 1 <= batch <= 5, "Batch must be 1-5"

    # Split 193 slugs into 5 batches
    batch_size = len(ALL_SLUGS) // 5
    start = (batch - 1) * batch_size
    if batch == 5:
        slugs = ALL_SLUGS[start:]  # last batch gets remainder
    else:
        slugs = ALL_SLUGS[start:start + batch_size]

    print(f"{'=' * 70}")
    print(f"  BATCH {batch}: Testing {len(slugs)} problems (idx {start}..{start + len(slugs) - 1})")
    print(f"{'=' * 70}")

    # Test at 2 terminal sizes for thoroughness
    sizes = [(120, 40), (80, 25)]

    from leetshell.app import LeetCodeApp

    for w, h in sizes:
        term = TT(w, h)
        app = LeetCodeApp()
        app.term = term
        await app._startup()
        await asyncio.sleep(2)

        print(f"\n  --- Terminal {w}x{h} ---")
        t0 = time.perf_counter()

        for slug in slugs:
            await test_problem(app, slug, term, w, h)

        elapsed = time.perf_counter() - t0
        print(f"  Completed {len(slugs)} problems at {w}x{h} in {elapsed:.1f}s")

        await app.client.close()

    print(f"\n{'=' * 70}")
    print(f"  BATCH {batch} TOTAL: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 70}")
    if FAIL > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
