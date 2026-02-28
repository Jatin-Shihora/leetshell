"""Comprehensive visual alignment and performance test.

Tests:
1. Visual: column alignment, symmetry, padding, no overflow/underflow
2. Performance: timing of every operation (startup, fetch, render, key, highlight)
3. Every screen: login, problem_list, problem_detail, test_result, submission_result
"""

import asyncio
import io
import re
import sys
import time


# ═══════════════════════════════════════════════════════════════════════
# TEST TERMINAL
# ═══════════════════════════════════════════════════════════════════════

class TestTerminal:
    """Minimal terminal that produces real ANSI escape codes without needing a TTY.

    blessed on Windows (jinxed) fails when stdout is not a TTY, even with
    force_styling=True. This class provides the same API used by our screens
    but with raw ANSI codes that work anywhere.
    """

    def __init__(self, width: int = 120, height: int = 40):
        self._width = width
        self._height = height

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def is_a_tty(self):
        return True

    @property
    def number_of_colors(self):
        return 256

    # ── Cursor movement ──

    def move_xy(self, x: int, y: int) -> str:
        return f"\x1b[{y + 1};{x + 1}H"

    @property
    def clear(self) -> str:
        return "\x1b[2J"

    @property
    def clear_eol(self) -> str:
        return "\x1b[K"

    @property
    def hidden_cursor(self):
        """Context manager stub."""
        class _Noop:
            def __enter__(self): return self
            def __exit__(self, *a): pass
        return _Noop()

    # ── Formatting (wrap text in ANSI codes) ──

    def _wrap(self, code: int, text: str) -> str:
        return f"\x1b[{code}m{text}\x1b[0m"

    def bold(self, text: str) -> str:
        return self._wrap(1, text)

    def dim(self, text: str) -> str:
        return self._wrap(2, text)

    def reverse(self, text: str) -> str:
        return self._wrap(7, text)

    def green(self, text: str) -> str:
        return self._wrap(32, text)

    def yellow(self, text: str) -> str:
        return self._wrap(33, text)

    def red(self, text: str) -> str:
        return self._wrap(31, text)

    def blue(self, text: str) -> str:
        return self._wrap(34, text)

    def magenta(self, text: str) -> str:
        return self._wrap(35, text)

    def cyan(self, text: str) -> str:
        return self._wrap(36, text)

    def white(self, text: str) -> str:
        return self._wrap(37, text)

    def bright_black(self, text: str) -> str:
        return self._wrap(90, text)

    def bright_red(self, text: str) -> str:
        return self._wrap(91, text)

    def bright_green(self, text: str) -> str:
        return self._wrap(92, text)

    def bright_cyan(self, text: str) -> str:
        return self._wrap(96, text)

    def length(self, text: str) -> int:
        """Visual width ignoring ANSI escape codes."""
        return len(re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text))


TERM = TestTerminal(120, 40)

PASS = 0
FAIL = 0
WARN = 0


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label} -- {detail}")


def warn(label, detail=""):
    global WARN
    WARN += 1
    print(f"  [WARN] {label} -- {detail}")


def benchmark(fn, label, *args, **kwargs):
    """Run fn and return (result, elapsed_ms)."""
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = (time.perf_counter() - start) * 1000
    return result, elapsed


async def abenchmark(coro, label):
    """Await coro and return (result, elapsed_ms)."""
    start = time.perf_counter()
    result = await coro
    elapsed = (time.perf_counter() - start) * 1000
    return result, elapsed


def capture_stdout():
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    return buf, old


def restore_stdout(old):
    sys.stdout = old


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
_MOVE_RE = re.compile(r'\x1b\[(\d+);(\d+)H')


def strip_ansi(text: str) -> str:
    """Remove all ANSI escape codes."""
    return _ANSI_RE.sub('', text)


def analyze_rendered_lines(buf_text: str) -> dict[int, list[tuple[int, str]]]:
    """Parse captured stdout into positioned text segments.

    Returns dict mapping row -> list of (col, plain_text) tuples.
    """
    segments = []
    pos = 0
    for match in _MOVE_RE.finditer(buf_text):
        start = match.start()
        if pos < start:
            segments.append(("text", buf_text[pos:start]))
        row = int(match.group(1)) - 1
        col = int(match.group(2)) - 1
        segments.append(("move", row, col))
        pos = match.end()
    if pos < len(buf_text):
        segments.append(("text", buf_text[pos:]))

    rows: dict[int, list[tuple[int, str]]] = {}
    cur_row, cur_col = 0, 0
    for seg in segments:
        if seg[0] == "move":
            cur_row = seg[1]
            cur_col = seg[2]
        elif seg[0] == "text":
            text = strip_ansi(seg[1])
            if text:
                if cur_row not in rows:
                    rows[cur_row] = []
                rows[cur_row].append((cur_col, text))

    return rows


def row_text(rows: dict, r: int) -> str:
    """Get full plain text for a given row."""
    if r not in rows:
        return ""
    return "".join(t for _, t in rows[r])


def all_text(rows: dict) -> str:
    """Get all plain text across all rows."""
    return "".join(row_text(rows, r) for r in sorted(rows.keys()))


def has_ansi(buf_text: str, code: int) -> bool:
    """Check if a specific ANSI code appears in raw output."""
    return f"\x1b[{code}m" in buf_text


# ═══════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════


async def test_login_screen_visual():
    print("\n=== LOGIN SCREEN: Visual ===")

    from leetshell.app import LeetCodeApp
    from leetshell.tui.login import LoginScreen

    app = LeetCodeApp()
    app.term = TERM

    login = LoginScreen(app)
    login.term = TERM
    await login.on_enter()

    buf, old = capture_stdout()
    _, t_r = benchmark(login.render, "login render")
    rendered = buf.getvalue()
    restore_stdout(old)
    print(f"  [PERF] Render: {t_r:.2f}ms")

    rows = analyze_rendered_lines(rendered)
    full = all_text(rows)

    check("Title 'LeetCode' shown", "LeetCode" in full or "leetcode" in full.lower())
    check("'Login via Browser' option", "Login via Browser" in full)
    check("'Manual Cookie Entry' option", "Manual Cookie Entry" in full)
    check("Cursor indicator '>' shown", ">" in full)
    check("Hint bar present", "navigate" in full.lower() or "enter" in full.lower())

    # Check reverse video on selected item (ANSI code 7)
    check("Selected item has reverse video", has_ansi(rendered, 7))

    # Check bold on title (ANSI code 1)
    check("Title has bold", has_ansi(rendered, 1))

    # Navigate down
    from blessed.keyboard import Keystroke
    await login.handle_key(Keystroke("j"))
    buf2, old2 = capture_stdout()
    login.render()
    restore_stdout(old2)
    check("Cursor moved to index 1", login._cursor == 1)

    # Navigate to browser step
    login._cursor = 0
    await login._on_menu_select()
    check("Step changed to 'browser'", login._step == "browser")

    buf3, old3 = capture_stdout()
    login.render()
    rendered3 = buf3.getvalue()
    restore_stdout(old3)
    full3 = all_text(analyze_rendered_lines(rendered3))
    check("Browser step shows 'Pick a browser'", "Pick a browser" in full3)

    await app.client.close()


async def test_problem_list_visual():
    print("\n=== PROBLEM LIST: Visual Alignment ===")

    from leetshell.app import LeetCodeApp
    app = LeetCodeApp()
    app.term = TERM

    _, t_startup = await abenchmark(app._startup(), "startup")
    print(f"  [PERF] Startup (session check + screen push): {t_startup:.1f}ms")

    screen = app.current_screen
    screen.term = TERM
    await asyncio.sleep(3)

    check("Problems loaded", len(screen._problems) > 0, f"got {len(screen._problems)}")

    if not screen._problems:
        print("  SKIPPING rest - no problems loaded")
        await app.client.close()
        return app

    # Render
    buf, old = capture_stdout()
    _, t_render = benchmark(screen.render, "render")
    rendered = buf.getvalue()
    restore_stdout(old)
    print(f"  [PERF] Full render: {t_render:.2f}ms")
    print(f"  [PERF] Render output size: {len(rendered)} bytes")

    rows = analyze_rendered_lines(rendered)

    # Row 0: Filter bar
    r0 = row_text(rows, 0)
    check("Filter bar present", len(r0) > 0)
    check("Filter bar has 'Difficulty'", "Difficulty" in r0)
    check("Filter bar uses reverse", has_ansi(rendered, 7))

    # Row 1: Table header
    r1 = row_text(rows, 1)
    check("Header has '#'", "#" in r1)
    check("Header has 'Title'", "Title" in r1)
    check("Header has 'Difficulty'", "Difficulty" in r1)
    check("Header has 'AC%'", "AC%" in r1)
    check("Header uses bold", has_ansi(rendered, 1))

    # Check column positions from header segments
    if 1 in rows:
        positions = [col for col, _ in rows[1]]
        check("Header starts at col 0", 0 in positions)
        # COL_STATUS=3, COL_ID=7 so '#' should be at col 3
        check("# column at position 3", 3 in positions, f"positions: {positions}")
        # Title at position 10 (3+7)
        check("Title column at position 10", 10 in positions, f"positions: {positions}")

    # Check data rows (rows 2+)
    data_rows_found = 0
    for r in range(2, min(30, TERM.height - 2)):
        rt = row_text(rows, r)
        if any(p.title[:8] in rt for p in screen._problems[:25] if p.title):
            data_rows_found += 1
    check("Data rows present (>=10)", data_rows_found >= 10, f"found {data_rows_found}")

    # Cursor (first data row = row 2) should be reverse video
    buf_r2 = rendered
    check("Cursor row has reverse video", has_ansi(buf_r2, 7))

    # Status bar (last row h-1=39)
    r_last = row_text(rows, TERM.height - 1)
    check("Status bar has page info 'pg'", "pg" in r_last)
    check("Status bar has 'j/k'", "j/k" in r_last)

    # === Column alignment across data rows ===
    print("\n  -- Column Alignment --")
    # Check that columns are consistently positioned across rows
    col_positions_per_row = []
    for r in range(2, min(8, len(screen._problems) + 2)):
        if r in rows:
            positions = sorted(set(col for col, _ in rows[r]))
            col_positions_per_row.append((r, positions))

    if len(col_positions_per_row) >= 2:
        # Non-cursor rows should all have same column positions
        # (cursor row is a single reversed line, no column splits)
        non_cursor_positions = [
            (r, ps) for r, ps in col_positions_per_row if r != 2
        ]
        if len(non_cursor_positions) >= 2:
            ref = non_cursor_positions[0][1]
            all_aligned = all(ps == ref for _, ps in non_cursor_positions[1:])
            check("Column positions consistent across rows", all_aligned,
                  f"ref={ref}, others={[ps for _, ps in non_cursor_positions[1:]]}")

    # === Scroll performance ===
    print("\n  -- Scroll Performance --")
    from blessed.keyboard import Keystroke

    times = []
    for _ in range(20):
        start = time.perf_counter()
        await screen.handle_key(Keystroke("j"))
        screen.dirty = True
        buf2, old2 = capture_stdout()
        screen.render()
        restore_stdout(old2)
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)

    avg_scroll = sum(times) / len(times)
    print(f"  [PERF] Scroll (j + render) x20: avg={avg_scroll:.2f}ms, "
          f"min={min(times):.2f}ms, max={max(times):.2f}ms")
    check("Scroll under 16ms (60fps)", avg_scroll < 16, f"avg={avg_scroll:.2f}ms")

    # Check cursor tracked scroll correctly
    check("Cursor at row 20 after 20 j presses", screen._cursor == 20,
          f"cursor={screen._cursor}")

    # === Difficulty filter ===
    print("\n  -- Difficulty Filter --")
    start = time.perf_counter()
    await screen.handle_key(Keystroke("d"))
    d_key_time = (time.perf_counter() - start) * 1000
    print(f"  [PERF] 'd' key handler: {d_key_time:.2f}ms")
    await asyncio.sleep(2)

    buf3, old3 = capture_stdout()
    _, t_filtered = benchmark(screen.render, "filtered render")
    restore_stdout(old3)
    print(f"  [PERF] Filtered render: {t_filtered:.2f}ms")

    # Reset difficulty
    await screen.handle_key(Keystroke("d"))
    await screen.handle_key(Keystroke("d"))
    await screen.handle_key(Keystroke("d"))
    await asyncio.sleep(2)

    await app.client.close()
    return app


async def test_problem_detail_visual():
    print("\n=== PROBLEM DETAIL: Visual + Editor Performance ===")

    from leetshell.app import LeetCodeApp
    from leetshell.tui.problem_detail import ProblemDetailScreen

    app = LeetCodeApp()
    app.term = TERM
    await app._startup()
    await asyncio.sleep(2)

    start = time.perf_counter()
    detail_screen = ProblemDetailScreen(app, "two-sum")
    detail_screen.term = TERM
    await app.push_screen(detail_screen)
    push_time = (time.perf_counter() - start) * 1000
    print(f"  [PERF] Push detail screen: {push_time:.2f}ms")

    await asyncio.sleep(3)

    check("Detail loaded", detail_screen._detail is not None)
    check("Editor created", detail_screen._editor is not None)
    check("Not loading", detail_screen._loading is False)

    if not detail_screen._detail:
        print("  SKIPPING rest - detail not loaded")
        await app.client.close()
        return

    # Set the editor's terminal too
    if detail_screen._editor:
        detail_screen._editor.term = TERM

    buf, old = capture_stdout()
    _, t_render = benchmark(detail_screen.render, "detail render")
    rendered = buf.getvalue()
    restore_stdout(old)
    print(f"  [PERF] Detail render: {t_render:.2f}ms")
    print(f"  [PERF] Render output size: {len(rendered)} bytes")

    rows = analyze_rendered_lines(rendered)

    # Row 0: header with problem title
    r0 = row_text(rows, 0)
    check("Header has problem '1.'", "1." in r0, f"header: {repr(r0[:60])}")
    check("Header has 'Two Sum'", "Two Sum" in r0)

    # Row 1: meta with difficulty
    r1 = row_text(rows, 1)
    check("Meta has 'Easy'", "Easy" in r1, f"meta: {repr(r1[:60])}")

    # Row 2: divider
    r2 = row_text(rows, 2)
    check("Divider has dashes", r2.count("-") > 10, f"row2: {repr(r2[:40])}")

    # Description area (rows 3-15 ish)
    desc_found = False
    for r in range(3, 20):
        rt = row_text(rows, r)
        if any(kw in rt.lower() for kw in ("array", "indices", "target", "nums")):
            desc_found = True
            break
    check("Description content visible", desc_found)

    # Editor area - should have code keywords
    editor_found = False
    for r in range(10, 35):
        rt = row_text(rows, r)
        if any(kw in rt for kw in ("class", "def ", "public", "func ", "fn ", "int ")):
            editor_found = True
            break
    check("Editor code visible", editor_found)

    # Check editor has line numbers
    line_num_found = False
    for r in range(10, 35):
        rt = row_text(rows, r)
        # Line numbers are right-justified like " 1 ", " 2 "
        if re.search(r'\d+\s', rt[:8]):
            line_num_found = True
            break
    check("Editor has line numbers", line_num_found)

    # Status bar
    r_last = row_text(rows, TERM.height - 1)
    check("Status has test hint", "test" in r_last.lower())
    check("Status has submit hint", "submit" in r_last.lower())
    check("Status has esc hint", "esc" in r_last.lower())

    # Editor header divider with language name
    full = all_text(rows)
    lang_slug = detail_screen._lang_slug
    check("Editor header has language divider", "---" in full)

    # === Editor performance ===
    print("\n  -- Editor Keystroke Performance --")
    editor = detail_screen._editor

    # Single character insert + relex
    times_insert = []
    for _ in range(50):
        start = time.perf_counter()
        editor._insert_char("x")
        editor._highlight_dirty = True
        editor._rehighlight()
        elapsed = (time.perf_counter() - start) * 1000
        times_insert.append(elapsed)
        editor._backspace()
        editor._highlight_dirty = True

    avg_insert = sum(times_insert) / len(times_insert)
    print(f"  [PERF] Insert+relex x50: avg={avg_insert:.2f}ms, max={max(times_insert):.2f}ms")
    check("Insert+relex under 16ms", avg_insert < 16, f"avg={avg_insert:.2f}ms")

    # Full render cycle (edit + render)
    times_render = []
    for _ in range(20):
        editor._insert_char("y")
        editor._highlight_dirty = True
        detail_screen.dirty = True
        start = time.perf_counter()
        buf2, old2 = capture_stdout()
        detail_screen.render()
        restore_stdout(old2)
        elapsed = (time.perf_counter() - start) * 1000
        times_render.append(elapsed)
        editor._backspace()
        editor._highlight_dirty = True

    avg_render = sum(times_render) / len(times_render)
    print(f"  [PERF] Full render cycle x20: avg={avg_render:.2f}ms, max={max(times_render):.2f}ms")
    check("Full render under 33ms (30fps)", avg_render < 33, f"avg={avg_render:.2f}ms")

    # Enter key
    times_enter = []
    for _ in range(10):
        start = time.perf_counter()
        editor._enter()
        editor._highlight_dirty = True
        editor._rehighlight()
        elapsed = (time.perf_counter() - start) * 1000
        times_enter.append(elapsed)
        editor._backspace()
        editor._highlight_dirty = True

    avg_enter = sum(times_enter) / len(times_enter)
    print(f"  [PERF] Enter+relex x10: avg={avg_enter:.2f}ms")

    # Arrow navigation
    times_nav = []
    for _ in range(50):
        start = time.perf_counter()
        editor._move_down()
        editor._move_right()
        elapsed = (time.perf_counter() - start) * 1000
        times_nav.append(elapsed)
    print(f"  [PERF] Arrow navigation x50: avg={sum(times_nav)/len(times_nav)*1000:.1f}us")

    # === Language cycling ===
    print("\n  -- Language Cycling --")
    old_lang = detail_screen._lang_slug
    start = time.perf_counter()
    detail_screen._action_next_lang()
    # Update editor terminal after lang change
    if detail_screen._editor:
        detail_screen._editor.term = TERM
    lang_time = (time.perf_counter() - start) * 1000
    new_lang = detail_screen._lang_slug
    print(f"  [PERF] Language cycle: {lang_time:.2f}ms ({old_lang} -> {new_lang})")
    check("Language changed", new_lang != old_lang, f"both={old_lang}")

    buf3, old3 = capture_stdout()
    _, t_lang_render = benchmark(detail_screen.render, "post-lang render")
    restore_stdout(old3)
    print(f"  [PERF] Post-language render: {t_lang_render:.2f}ms")

    # === Description toggle ===
    print("\n  -- Description Toggle --")
    start = time.perf_counter()
    detail_screen._view_mode = "editor"
    detail_screen.dirty = True
    buf4, old4 = capture_stdout()
    detail_screen.render()
    restore_stdout(old4)
    toggle_time = (time.perf_counter() - start) * 1000
    print(f"  [PERF] Toggle to editor + render: {toggle_time:.2f}ms")
    detail_screen._view_mode = "split"

    await app.client.close()


async def test_result_screens_visual():
    print("\n=== RESULT SCREENS: Visual ===")

    from leetshell.app import LeetCodeApp
    from leetshell.models.submission import TestResult, TestCaseResult, SubmissionResult
    from leetshell.tui.test_result import TestResultScreen
    from leetshell.tui.submission_result import SubmissionResultScreen

    app = LeetCodeApp()
    app.term = TERM

    # --- Test Result: All pass ---
    print("\n  -- TestResultScreen (all pass) --")
    tr_pass = TestResult(
        run_success=True, status_code=10, status_msg="Accepted",
        total_correct=3, total_testcases=3,
        runtime="4 ms", memory="8.2 MB",
        test_cases=[
            TestCaseResult(input_data="[2,7,11,15]\n9", expected="[0,1]", actual="[0,1]", passed=True),
            TestCaseResult(input_data="[3,2,4]\n6", expected="[1,2]", actual="[1,2]", passed=True),
            TestCaseResult(input_data="[3,3]\n6", expected="[0,1]", actual="[0,1]", passed=True),
        ],
    )
    screen = TestResultScreen(app, tr_pass, "two-sum")
    screen.term = TERM

    buf, old = capture_stdout()
    _, t_r = benchmark(screen.render, "test result render")
    rendered = buf.getvalue()
    restore_stdout(old)
    print(f"  [PERF] Render: {t_r:.2f}ms")

    rows = analyze_rendered_lines(rendered)
    full = all_text(rows)

    check("Title 'Test Results' shown", "Test Results" in full)
    check("All 3 PASS icons", full.count("PASS") == 3, f"count={full.count('PASS')}")
    check("Runtime '4 ms' shown", "4 ms" in full)
    check("Memory '8.2 MB' shown", "8.2 MB" in full)
    check("Status bar has [s] submit", "submit" in full.lower())
    check("Uses green color (code 32)", has_ansi(rendered, 32))
    check("Title uses bold", has_ansi(rendered, 1))

    # --- Test Result: Failure ---
    print("\n  -- TestResultScreen (with failure) --")
    tr_fail = TestResult(
        run_success=True, status_code=10, status_msg="",
        total_correct=1, total_testcases=2,
        runtime="3 ms", memory="7 MB",
        test_cases=[
            TestCaseResult(input_data="[2,7]", expected="[0,1]", actual="[0,1]", passed=True),
            TestCaseResult(input_data="[3,4]", expected="[0,1]", actual="[1,0]", passed=False),
        ],
    )
    screen2 = TestResultScreen(app, tr_fail, "two-sum")
    screen2.term = TERM
    buf2, old2 = capture_stdout()
    screen2.render()
    rendered2 = buf2.getvalue()
    restore_stdout(old2)

    full2 = all_text(analyze_rendered_lines(rendered2))
    check("PASS icon shown", "PASS" in full2)
    check("FAIL icon shown", "FAIL" in full2)
    check("Expected [0,1] shown", "[0,1]" in full2)
    check("Actual [1,0] shown", "[1,0]" in full2)
    check("Uses red color for FAIL (code 31)", has_ansi(rendered2, 31))

    # --- Test Result: Compile Error ---
    print("\n  -- TestResultScreen (compile error) --")
    tr_ce = TestResult(
        run_success=False, status_code=20, status_msg="Compile Error",
        compile_error="Line 5: error: expected ';' before '}'\n  }",
    )
    screen3 = TestResultScreen(app, tr_ce, "two-sum")
    screen3.term = TERM
    buf3, old3 = capture_stdout()
    screen3.render()
    rendered3 = buf3.getvalue()
    restore_stdout(old3)

    full3 = all_text(analyze_rendered_lines(rendered3))
    check("'Compile Error' label shown", "Compile Error" in full3)
    check("Error detail 'expected' shown", "expected" in full3)

    # --- Submission Result: Accepted ---
    print("\n  -- SubmissionResultScreen (accepted) --")
    sr = SubmissionResult(
        status_code=10, status_msg="Accepted", run_success=True,
        total_correct=100, total_testcases=100,
        runtime="4 ms", memory="8.2 MB",
        runtime_percentile=95.5, memory_percentile=80.2,
    )
    sub_screen = SubmissionResultScreen(app, sr)
    sub_screen.term = TERM
    buf4, old4 = capture_stdout()
    _, t_sr = benchmark(sub_screen.render, "submission render")
    rendered4 = buf4.getvalue()
    restore_stdout(old4)
    print(f"  [PERF] Render: {t_sr:.2f}ms")

    full_sr = all_text(analyze_rendered_lines(rendered4))
    check("'Accepted' shown", "Accepted" in full_sr)
    check("'100/100' shown", "100/100" in full_sr)
    check("Runtime '4 ms' shown", "4 ms" in full_sr)
    check("Runtime percentile '95.5%'", "95.5%" in full_sr)
    check("Memory percentile '80.2%'", "80.2%" in full_sr)
    check("Uses green color", has_ansi(rendered4, 32))

    # --- Submission Result: Wrong Answer ---
    print("\n  -- SubmissionResultScreen (wrong answer) --")
    sr_wa = SubmissionResult(
        status_code=11, status_msg="Wrong Answer", run_success=False,
        total_correct=50, total_testcases=100,
        runtime="10 ms",
        input_data="[1,2,3]", expected_output="[3,2,1]", code_output="[1,2,3]",
    )
    sub2 = SubmissionResultScreen(app, sr_wa)
    sub2.term = TERM
    buf5, old5 = capture_stdout()
    sub2.render()
    rendered5 = buf5.getvalue()
    restore_stdout(old5)

    full_wa = all_text(analyze_rendered_lines(rendered5))
    check("'Wrong Answer' shown", "Wrong Answer" in full_wa)
    check("'50/100' shown", "50/100" in full_wa)
    check("Input '[1,2,3]' shown", "[1,2,3]" in full_wa)
    check("Expected '[3,2,1]' shown", "[3,2,1]" in full_wa)

    # --- Submission Result: Runtime Error ---
    print("\n  -- SubmissionResultScreen (runtime error) --")
    sr_re = SubmissionResult(
        status_code=15, status_msg="Runtime Error", run_success=False,
        total_correct=5, total_testcases=10,
        runtime_error="AddressSanitizer: heap-buffer-overflow",
    )
    sub3 = SubmissionResultScreen(app, sr_re)
    sub3.term = TERM
    buf6, old6 = capture_stdout()
    sub3.render()
    rendered6 = buf6.getvalue()
    restore_stdout(old6)

    full_re = all_text(analyze_rendered_lines(rendered6))
    check("'Runtime Error' shown", "Runtime Error" in full_re)
    check("'AddressSanitizer' shown", "AddressSanitizer" in full_re)

    # --- Scroll performance ---
    print("\n  -- Result Screen Scroll Performance --")
    from blessed.keyboard import Keystroke

    big_tr = TestResult(
        run_success=True, status_code=10, status_msg="Accepted",
        total_correct=20, total_testcases=20,
        runtime="10 ms", memory="20 MB",
        test_cases=[
            TestCaseResult(
                input_data=f"input_{i}" * 5,
                expected=f"expected_{i}" * 3,
                actual=f"actual_{i}" * 3,
                passed=(i % 3 != 0),
            )
            for i in range(20)
        ],
    )
    big_screen = TestResultScreen(app, big_tr, "test")
    big_screen.term = TERM
    print(f"  Lines to scroll: {len(big_screen._lines)}")

    scroll_times = []
    for _ in range(30):
        start = time.perf_counter()
        await big_screen.handle_key(Keystroke("j"))
        big_screen.dirty = True
        buf7, old7 = capture_stdout()
        big_screen.render()
        restore_stdout(old7)
        elapsed = (time.perf_counter() - start) * 1000
        scroll_times.append(elapsed)

    avg_s = sum(scroll_times) / len(scroll_times)
    print(f"  [PERF] Scroll result x30: avg={avg_s:.2f}ms, max={max(scroll_times):.2f}ms")
    check("Result scroll under 16ms", avg_s < 16, f"avg={avg_s:.2f}ms")

    await app.client.close()


async def test_editor_highlighting_visual():
    print("\n=== EDITOR: Syntax Highlighting ===")

    from leetshell.tui.editor import CodeEditor

    test_cases = {
        "python": "def hello():\n    x = 42\n    print('world')\n    return True",
        "cpp": "int main() {\n    int x = 42;\n    std::cout << \"hello\";\n    return 0;\n}",
        "java": "class Solution {\n    public int solve(int n) {\n        return n * 2;\n    }\n}",
        "javascript": "function solve(nums) {\n    const map = {};\n    return nums.filter(x => x > 0);\n}",
        "go": "func main() {\n    x := 42\n    fmt.Println(\"hello\")\n}",
        "rust": "fn main() {\n    let x: i32 = 42;\n    println!(\"hello\");\n}",
    }

    for lang, code in test_cases.items():
        editor = CodeEditor(TERM, lang)
        editor.set_text(code)

        start = time.perf_counter()
        editor._rehighlight()
        lex_time = (time.perf_counter() - start) * 1000

        total_tokens = sum(len(line) for line in editor._highlighted)
        colored_tokens = sum(
            1 for line in editor._highlighted
            for color, _ in line if color
        )

        check(f"{lang}: has tokens", total_tokens > 0, f"tokens={total_tokens}")
        check(f"{lang}: has colored tokens", colored_tokens > 0, f"colored={colored_tokens}")
        print(f"  [PERF] {lang} lex ({editor.line_count} lines): {lex_time:.2f}ms, "
              f"{total_tokens} tokens ({colored_tokens} colored)")

    # Render test for each language to check colors appear in output
    print("\n  -- Render Color Check --")
    for lang, code in test_cases.items():
        editor = CodeEditor(TERM, lang)
        editor.set_text(code)
        buf, old = capture_stdout()
        editor.render(0, 0, 80, 10)
        rendered = buf.getvalue()
        restore_stdout(old)
        has_color = any(has_ansi(rendered, c) for c in [31, 32, 33, 34, 35, 36, 90])
        check(f"{lang}: render produces color codes", has_color)

    # Stress test: 200-line Python file
    print("\n  -- Stress Test: 200-line file --")
    big_code = "\n".join([
        line for i in range(30) for line in [
            f"def func_{i}(x, y):",
            f"    # Process item {i}",
            f"    result = x * y + {i}",
            f"    if result > 100:",
            f"        return 'large'",
            f"    return result",
            "",
        ]
    ])

    big_editor = CodeEditor(TERM, "python")
    big_editor.set_text(big_code)

    times = []
    for _ in range(50):
        big_editor._highlight_dirty = True
        start = time.perf_counter()
        big_editor._rehighlight()
        times.append((time.perf_counter() - start) * 1000)

    avg = sum(times) / len(times)
    print(f"  [PERF] {big_editor.line_count}-line Python relex x50: avg={avg:.2f}ms, max={max(times):.2f}ms")
    check("200-line relex under 20ms", avg < 20, f"avg={avg:.2f}ms")

    # Render performance
    render_times = []
    for _ in range(20):
        big_editor._insert_char("z")
        big_editor._highlight_dirty = True
        start = time.perf_counter()
        buf, old = capture_stdout()
        big_editor.render(0, 0, 120, 35)
        restore_stdout(old)
        render_times.append((time.perf_counter() - start) * 1000)
        big_editor._backspace()
        big_editor._highlight_dirty = True

    avg_r = sum(render_times) / len(render_times)
    print(f"  [PERF] {big_editor.line_count}-line render x20: avg={avg_r:.2f}ms, max={max(render_times):.2f}ms")
    check("200-line render under 33ms", avg_r < 33, f"avg={avg_r:.2f}ms")


async def test_symmetry():
    """Check visual symmetry: consistent padding, alignment, no overflow."""
    print("\n=== SYMMETRY & LAYOUT CHECKS ===")

    from leetshell.tui.core import pad_right, truncate

    # pad_right always produces exact width
    for w in [5, 10, 20, 80, 120]:
        result = pad_right("hello", w)
        check(f"pad_right('hello', {w}) = {w} chars", len(result) == w, f"got {len(result)}")

    # truncate never exceeds width
    for w in [3, 5, 10, 20]:
        result = truncate("this is a very long string that should be cut", w)
        check(f"truncate(long, {w}) <= {w} chars", len(result) <= w, f"got {len(result)}")

    # truncate preserves short strings
    check("truncate('hi', 10) = 'hi'", truncate("hi", 10) == "hi")

    # pad_right with empty
    check("pad_right('', 5) = 5 spaces", len(pad_right("", 5)) == 5)

    # Edge cases
    check("truncate('', 0) = ''", truncate("", 0) == "")
    check("pad_right('', 0) = ''", pad_right("", 0) == "")
    check("truncate('abc', 3) = 'abc'", truncate("abc", 3) == "abc")
    check("truncate('abcd', 3) = 'abc'", truncate("abcd", 3) == "abc")


async def main():
    print("=" * 70)
    print("  VISUAL ALIGNMENT & PERFORMANCE TEST SUITE")
    print("=" * 70)

    await test_symmetry()
    await test_login_screen_visual()
    await test_editor_highlighting_visual()
    await test_result_screens_visual()
    await test_problem_list_visual()
    await test_problem_detail_visual()

    print("\n" + "=" * 70)
    print(f"  RESULTS: {PASS} passed, {FAIL} failed, {WARN} warnings")
    print("=" * 70)

    if FAIL > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
