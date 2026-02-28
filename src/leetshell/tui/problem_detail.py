from __future__ import annotations

import asyncio
import re
import sys
import html2text

from leetshell.api.client import AuthenticationError
from leetshell.config import save_config
from leetshell.constants import SLUG_TO_LANGUAGE, LANG_SLUG_TO_PYGMENTS
from leetshell.editor import get_solution_path
from leetshell.models.problem import ProblemDetail
from leetshell.tui.core import (
    Screen, write_at, clear_screen, clear_line, pad_right, truncate,
    write_row, fmt, flush,
)
from leetshell.tui.editor import CodeEditor

# Shared html2text converter
_h2t_instance: html2text.HTML2Text | None = None


def _get_h2t() -> html2text.HTML2Text:
    global _h2t_instance
    if _h2t_instance is None:
        _h2t_instance = html2text.HTML2Text()
        _h2t_instance.ignore_links = False
        _h2t_instance.ignore_images = True
        _h2t_instance.body_width = 0
    return _h2t_instance


# ── Box-drawing description formatter ─────────────────────────────


def _wrap_for_box(text: str, max_w: int) -> list[str]:
    """Word-wrap a single line to fit within max_w chars."""
    if len(text) <= max_w:
        return [text]
    indent = len(text) - len(text.lstrip())
    prefix = text[:indent]
    result: list[str] = []
    rest = text
    while len(rest) > max_w:
        cut = rest.rfind(" ", 0, max_w)
        if cut <= indent:
            cut = max_w
        result.append(rest[:cut])
        rest = prefix + rest[cut:].lstrip()
    if rest:
        result.append(rest)
    return result


def _make_box(title: str, content_lines: list[str], box_w: int) -> list[str]:
    """Build a box with a title bar and content lines."""
    inner_w = box_w - 4  # "│ " + content + " │"
    result: list[str] = []

    # Top: ┌─ Title ──────────┐
    title_str = f"─ {title} "
    fill = box_w - 2 - len(title_str)
    result.append("┌" + title_str + "─" * max(0, fill) + "┐")

    for cl in content_lines:
        text = cl.rstrip()
        if not text:
            result.append("│" + " " * (box_w - 2) + "│")
            continue
        for wl in _wrap_for_box(text, inner_w):
            pad = inner_w - len(wl)
            result.append("│ " + wl + " " * max(0, pad) + " │")

    # Bottom: └──────────────────┘
    result.append("└" + "─" * (box_w - 2) + "┘")
    return result


def _format_with_boxes(lines: list[str], box_w: int) -> list[str]:
    """Add box-drawing borders around Example and Constraints sections."""
    result: list[str] = []
    i = 0
    examples_started = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # ── Detect "Example N:" ──
        if re.match(r"Example\s+\d+\s*:", stripped):
            if not examples_started:
                examples_started = True
                label = " Examples "
                side_l = (box_w - len(label)) // 2
                side_r = box_w - side_l - len(label)
                result.append("─" * side_l + label + "─" * side_r)
                result.append("")

            title = stripped.rstrip(":").strip()  # "Example 1"
            content: list[str] = []
            i += 1
            # Skip blank lines after header
            while i < len(lines) and not lines[i].strip():
                i += 1
            # Collect until next Example, Constraints, or end
            while i < len(lines):
                s = lines[i].strip()
                if re.match(r"Example\s+\d+\s*:", s):
                    break
                if re.match(r"Constraints?\s*:?", s, re.IGNORECASE):
                    break
                content.append(lines[i])
                i += 1
            # Trim trailing blanks
            while content and not content[-1].strip():
                content.pop()

            result.extend(_make_box(title, content, box_w))
            result.append("")
            continue

        # ── Detect "Constraints:" ──
        if re.match(r"Constraints?\s*:?$", stripped, re.IGNORECASE):
            content = []
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            while i < len(lines):
                s = lines[i].strip()
                if re.match(r"(Follow[\s-]?up|Note)\s*:", s, re.IGNORECASE):
                    break
                content.append(lines[i])
                i += 1
            while content and not content[-1].strip():
                content.pop()

            result.append("")
            result.extend(_make_box("Constraints", content, box_w))
            # Continue to pick up Follow-up etc.
            continue

        result.append(line)
        i += 1

    return result


def _rewrap_lines(lines: list[str], max_w: int) -> list[str]:
    """Re-wrap lines to fit within max_w, preserving indentation."""
    result: list[str] = []
    for line in lines:
        if len(line) <= max_w:
            result.append(line)
        else:
            indent = len(line) - len(line.lstrip())
            prefix = line[:indent]
            rest = line
            while len(rest) > max_w:
                cut = rest.rfind(" ", indent, max_w)
                if cut <= indent:
                    cut = max_w
                result.append(rest[:cut])
                rest = prefix + rest[cut:].lstrip()
            if rest:
                result.append(rest)
    return result


class ProblemDetailScreen(Screen):
    def __init__(self, app, title_slug: str) -> None:
        super().__init__(app)
        self._title_slug = title_slug
        self._detail: ProblemDetail | None = None
        self._lang_slug: str = ""
        self._lang_index: int = 0
        self._view_mode: str = "split"  # "desc" | "split" | "editor"
        self._dirty = False
        self._loading = True
        self._editor: CodeEditor | None = None

        # Description
        self._desc_lines: list[str] = []      # formatted with boxes (full-screen desc)
        self._desc_lines_raw: list[str] = []   # plain cleaned lines (split view)
        self._desc_scroll: int = 0

    async def on_enter(self) -> None:
        self.invalidate()
        if self._detail is None:
            asyncio.create_task(self._fetch_detail())

    # ── Data fetching ────────────────────────────────────────────────

    async def _fetch_detail(self) -> None:
        try:
            detail = await self.app.problem_service.get_problem_detail(
                self._title_slug
            )
            self._detail = detail

            if detail.paid_only and not detail.content:
                self._loading = False
                self._desc_lines = ["Premium problem. Content not available."]
                self._desc_lines_raw = list(self._desc_lines)
                self.invalidate()
                return

            # Parse description - wrap at terminal width for proper display
            h2t = _get_h2t()
            h2t.body_width = max(40, self.term.width - 4)
            content = detail.content or ""
            # Convert <sup> to ^ for readable exponents (e.g. 2^31)
            content = re.sub(r"<sup>(\w+)</sup>", r"^\1", content)
            md_text = h2t.handle(content) if content else "No content."
            # Strip markdown bold markers for clean terminal display
            md_text = md_text.replace("**", "")
            # Collapse consecutive blank lines and strip trailing whitespace
            raw_lines = md_text.split("\n")
            cleaned: list[str] = []
            prev_blank = False
            for line in raw_lines:
                stripped = line.rstrip()
                is_blank = not stripped
                if is_blank and prev_blank:
                    continue  # skip consecutive blank lines
                cleaned.append(stripped)
                prev_blank = is_blank
            # Remove leading/trailing blank lines
            while cleaned and not cleaned[0]:
                cleaned.pop(0)
            while cleaned and not cleaned[-1]:
                cleaned.pop()
            # Hard-wrap any remaining long lines (indented code/list items)
            max_w = max(40, self.term.width - 4)
            wrapped: list[str] = []
            for line in cleaned:
                if len(line) <= max_w:
                    wrapped.append(line)
                else:
                    # Preserve leading indent when wrapping
                    indent = len(line) - len(line.lstrip())
                    prefix = line[:indent]
                    rest = line
                    while len(rest) > max_w:
                        # Find last space before max_w
                        cut = rest.rfind(" ", indent, max_w)
                        if cut <= indent:
                            cut = max_w  # no space found, hard cut
                        wrapped.append(rest[:cut])
                        rest = prefix + rest[cut:].lstrip()
                    if rest:
                        wrapped.append(rest)
            # Save raw lines for split view (before box formatting)
            self._desc_lines_raw = list(wrapped)
            # Format with box-drawing borders for examples & constraints
            avail_w = max(40, self.term.width - 2)
            self._desc_lines = _format_with_boxes(wrapped, avail_w)

            # Set language
            self._lang_slug = self.app.user_config.preferences.language
            if detail.code_snippets:
                slugs = [s.lang_slug for s in detail.code_snippets]
                if self._lang_slug in slugs:
                    self._lang_index = slugs.index(self._lang_slug)
                else:
                    self._lang_index = 0
                    self._lang_slug = slugs[0]

            # Load code and create editor
            code = self._load_code()
            pygments_lang = LANG_SLUG_TO_PYGMENTS.get(self._lang_slug, "text")
            self._editor = CodeEditor(self.term, pygments_lang)
            self._editor.set_text(code)

            self._loading = False
            self.invalidate()

        except AuthenticationError:
            self._loading = False
            self.app.show_login_on_auth_error()
        except Exception as e:
            self._loading = False
            self.app.notify(f"Error: {e}")
            self.invalidate()

    def _load_code(self) -> str:
        if not self._detail:
            return ""
        path = get_solution_path(self._title_slug, self._lang_slug)
        if path.exists():
            return path.read_text(encoding="utf-8")
        snippet = self._detail.get_snippet(self._lang_slug)
        return snippet.code if snippet else ""

    def _save_code(self) -> None:
        if not self._dirty or self._editor is None:
            return
        self._dirty = False
        code = self._editor.get_text()
        path = get_solution_path(self._title_slug, self._lang_slug)
        path.write_text(code, encoding="utf-8")

    # ── Rendering ─────────────────────────────────────────────────────

    def render(self) -> None:
        t = self.term
        w = t.width
        h = t.height

        if self._loading:
            clear_screen(t)
            write_at(t, w // 2 - 5, h // 2, fmt(t, "dim", "loading..."))
            flush()
            return

        if not self._detail:
            clear_screen(t)
            write_at(t, 2, 2, "No data.")
            flush()
            return

        detail = self._detail

        # Row 0: Header (title) - plain text, then bold
        header = truncate(f"{detail.frontend_id}. {detail.title}", w)
        write_row(t, 0, header, "bold", fill=True)

        # Row 1: Meta (difficulty + tags) - write each part separately
        diff = detail.difficulty
        diff_color = {"Easy": "green", "Medium": "yellow", "Hard": "red"}.get(diff, "")
        tags = ", ".join(detail.topic_tags[:5]) if detail.topic_tags else ""

        clear_line(t, 1)
        sys.stdout.write(t.move_xy(0, 1) + fmt(t, diff_color, diff))
        if tags:
            sys.stdout.write(t.move_xy(len(diff) + 2, 1) + fmt(t, "dim", truncate(tags, w - len(diff) - 2)))

        # Row 2: Divider
        write_row(t, 2, "-" * w, "dim")

        status_row = h - 1
        content_height = h - 4  # rows 3 to h-2

        if self._view_mode == "desc":
            # ── Description mode: full screen for description ──
            total_desc = len(self._desc_lines)
            desc_height = content_height
            visible_lines = self._desc_lines[self._desc_scroll: self._desc_scroll + desc_height]
            for i in range(desc_height):
                row_y = 3 + i
                clear_line(t, row_y)
                if i < len(visible_lines):
                    write_at(t, 1, row_y, truncate(visible_lines[i], w - 2))

            # Scroll hint if content overflows
            has_more = (self._desc_scroll + desc_height) < total_desc or self._desc_scroll > 0
            if has_more:
                remaining = total_desc - self._desc_scroll - desc_height
                if remaining > 0:
                    hint = f"[scroll: ^up/^dn, {remaining} more]"
                else:
                    hint = "[scroll: ^up/^dn]"
                hint_x = max(0, w - len(hint) - 1)
                write_at(t, hint_x, 3 + desc_height - 1, fmt(t, "dim", hint))

        elif self._view_mode == "split":
            # ── Split mode: description left ~40%, editor right ~60% ──
            desc_w = w * 2 // 5
            editor_w = w - desc_w - 1  # 1 col for │ divider

            # Re-wrap raw description lines to fit in the narrower pane
            desc_text_w = max(10, desc_w - 2)  # 1 col left margin + 1 col right pad
            split_desc = _rewrap_lines(self._desc_lines_raw, desc_text_w)

            # Description pane (left)
            total_desc = len(split_desc)
            visible_lines = split_desc[self._desc_scroll: self._desc_scroll + content_height]
            for i in range(content_height):
                row_y = 3 + i
                if i < len(visible_lines):
                    line_text = truncate(visible_lines[i], desc_text_w)
                    # Write left margin + text + padding up to divider
                    padded = " " + line_text
                    padding = desc_w - len(padded)
                    if padding > 0:
                        padded += " " * padding
                    sys.stdout.write(t.move_xy(0, row_y) + padded)
                else:
                    sys.stdout.write(t.move_xy(0, row_y) + " " * desc_w)
                # Draw divider
                sys.stdout.write(fmt(t, "dim", "│"))

            # Scroll hint for description pane
            has_more = (self._desc_scroll + content_height) < total_desc or self._desc_scroll > 0
            if has_more:
                remaining = total_desc - self._desc_scroll - content_height
                if remaining > 0:
                    hint = f"[{remaining} more]"
                else:
                    hint = "[scroll]"
                hint_x = max(0, desc_w - len(hint) - 1)
                write_at(t, hint_x, 3 + content_height - 1, fmt(t, "dim", hint))

            # Editor pane (right) - language header + code
            lang = SLUG_TO_LANGUAGE.get(self._lang_slug, self._lang_slug)
            hdr_text = f"--- {lang.lower()} " + "-" * max(0, editor_w - len(lang) - 5)
            write_at(t, desc_w + 1, 3, fmt(t, "dim", truncate(hdr_text, editor_w)))
            if self._editor and content_height > 1:
                self._editor.render(desc_w + 1, 4, editor_w, content_height - 1)

        else:
            # ── Editor mode: full screen for code editor ──
            lang = SLUG_TO_LANGUAGE.get(self._lang_slug, self._lang_slug)
            hdr_text = f"--- {lang.lower()} " + "-" * max(0, w - len(lang) - 5)
            write_row(t, 3, truncate(hdr_text, w), "dim", fill=True)

            editor_start = 4
            editor_height = status_row - editor_start
            if self._editor and editor_height > 0:
                self._editor.render(0, editor_start, w, editor_height)

        # Status bar
        notif = self.app.get_notification()
        if notif:
            write_row(t, status_row, notif, "dim", fill=True)
        else:
            if self._view_mode == "desc":
                status = "^d split view  arrows scroll  esc back"
            elif self._view_mode == "split":
                status = "^t test  ^s submit  ^l lang  ^d editor  ^u/^r undo/redo  c-up/dn scroll  esc back"
            else:
                status = "^t test  ^s submit  ^l lang  ^d description  ^u/^r undo/redo  esc back"
            write_row(t, status_row, status, "dim", fill=True)

        flush()

    # ── Key handling ──────────────────────────────────────────────────

    async def handle_key(self, key) -> None:
        # Ctrl+T: test
        if key == "\x14":
            await self._action_test()
            return

        # Ctrl+S: submit
        if key == "\x13":
            await self._action_submit()
            return

        # Ctrl+L: cycle language
        if key == "\x0c":
            self._action_next_lang()
            return

        # Ctrl+D: cycle view mode desc → split → editor → desc
        if key == "\x04":
            cycle = {"desc": "split", "split": "editor", "editor": "desc"}
            self._view_mode = cycle[self._view_mode]
            self.invalidate()
            return

        # Esc: go back
        if key.name == "KEY_ESCAPE":
            self._save_code()
            await self.app.pop_screen()
            return

        if self._view_mode == "desc":
            # Description mode: arrow keys scroll
            if key.name in ("kUP5", "kUP3", "KEY_UP"):
                if self._desc_scroll > 0:
                    self._desc_scroll -= 1
                    self.invalidate()
                return
            if key.name in ("kDN5", "kDN3", "KEY_DOWN"):
                content_height = max(1, self.term.height - 4)
                max_scroll = max(0, len(self._desc_lines) - content_height)
                if self._desc_scroll < max_scroll:
                    self._desc_scroll += 1
                    self.invalidate()
                return
            if key.name == "KEY_PGUP":
                content_height = max(1, self.term.height - 4)
                self._desc_scroll = max(0, self._desc_scroll - content_height)
                self.invalidate()
                return
            if key.name == "KEY_PGDOWN":
                content_height = max(1, self.term.height - 4)
                max_scroll = max(0, len(self._desc_lines) - content_height)
                self._desc_scroll = min(max_scroll, self._desc_scroll + content_height)
                self.invalidate()
                return

        elif self._view_mode == "split":
            # Split mode: Ctrl+Up/Down scroll description, everything else → editor
            if key.name in ("kUP5", "kUP3"):
                if self._desc_scroll > 0:
                    self._desc_scroll -= 1
                    self.invalidate()
                return
            if key.name in ("kDN5", "kDN3"):
                content_height = max(1, self.term.height - 4)
                desc_w = self.term.width * 2 // 5
                desc_text_w = max(10, desc_w - 2)
                split_lines = _rewrap_lines(self._desc_lines_raw, desc_text_w)
                max_scroll = max(0, len(split_lines) - content_height)
                if self._desc_scroll < max_scroll:
                    self._desc_scroll += 1
                    self.invalidate()
                return
            if key.name == "KEY_PGUP":
                content_height = max(1, self.term.height - 4)
                self._desc_scroll = max(0, self._desc_scroll - content_height)
                self.invalidate()
                return
            if key.name == "KEY_PGDOWN":
                content_height = max(1, self.term.height - 4)
                desc_w = self.term.width * 2 // 5
                desc_text_w = max(10, desc_w - 2)
                split_lines = _rewrap_lines(self._desc_lines_raw, desc_text_w)
                max_scroll = max(0, len(split_lines) - content_height)
                self._desc_scroll = min(max_scroll, self._desc_scroll + content_height)
                self.invalidate()
                return
            # All other keys (arrows, shift+arrows, typing, etc.) → editor
            if self._editor:
                consumed = self._editor.handle_key(key)
                if consumed:
                    self._dirty = True
                    self.invalidate()

        else:
            # Editor mode: pass keys to editor
            if self._editor:
                consumed = self._editor.handle_key(key)
                if consumed:
                    self._dirty = True
                    self.invalidate()

    # ── Actions ───────────────────────────────────────────────────────

    async def _action_test(self) -> None:
        if not self._detail:
            return
        self._save_code()
        code = self._editor.get_text() if self._editor else ""
        if not code.strip():
            self.app.notify("No code to test.")
            return
        self.app.notify("Running tests...")
        self.invalidate()

        async def _run():
            try:
                test_input = "\n".join(self._detail.example_testcases)
                result = await self.app.submission_service.test(
                    title_slug=self._title_slug,
                    question_id=self._detail.question_id,
                    lang=self._lang_slug,
                    code=code,
                    test_input=test_input,
                )
                from leetshell.tui.test_result import TestResultScreen
                screen = TestResultScreen(self.app, result, self._title_slug)
                screen.on_dismiss = self._on_test_dismissed
                await self.app.push_screen(screen)
            except AuthenticationError:
                self.app.show_login_on_auth_error()
            except Exception as e:
                self.app.notify(f"Test error: {e}")
                self.invalidate()

        asyncio.create_task(_run())

    async def _action_submit(self) -> None:
        if not self._detail:
            return
        self._save_code()
        code = self._editor.get_text() if self._editor else ""
        if not code.strip():
            self.app.notify("No code to submit.")
            return
        self.app.notify("Submitting...")
        self.invalidate()

        async def _run():
            try:
                result = await self.app.submission_service.submit(
                    title_slug=self._title_slug,
                    question_id=self._detail.question_id,
                    lang=self._lang_slug,
                    code=code,
                )
                from leetshell.tui.submission_result import SubmissionResultScreen
                screen = SubmissionResultScreen(self.app, result)
                screen.on_dismiss = self._on_submission_dismissed
                await self.app.push_screen(screen)
            except AuthenticationError:
                self.app.show_login_on_auth_error()
            except Exception as e:
                self.app.notify(f"Submit error: {e}")
                self.invalidate()

        asyncio.create_task(_run())

    async def _on_test_dismissed(self, action: str | None) -> None:
        if action == "submit":
            await self._action_submit()

    async def _on_submission_dismissed(self, action: str | None) -> None:
        if action == "list":
            await self.app.pop_screen()

    def _action_next_lang(self) -> None:
        if not self._detail or not self._detail.code_snippets:
            return
        self._save_code()
        self._lang_index = (self._lang_index + 1) % len(self._detail.code_snippets)
        self._lang_slug = self._detail.code_snippets[self._lang_index].lang_slug

        code = self._load_code()
        pygments_lang = LANG_SLUG_TO_PYGMENTS.get(self._lang_slug, "text")
        if self._editor:
            self._editor.set_language(pygments_lang)
            self._editor.set_text(code)
        self._dirty = False

        self.app.user_config.preferences.language = self._lang_slug
        save_config(self.app.user_config)
        self.invalidate()
