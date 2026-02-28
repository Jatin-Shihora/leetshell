# Contributing

We'd love your help making leetshell better. Whether it's a bug fix, new feature, or documentation improvement, all contributions are welcome.

## Issues

Bug reports, feature requests, and questions are all welcome as [GitHub issues](https://github.com/Jatin-Shihora/leetshell/issues).

When reporting a bug, please include:
- Your OS and terminal emulator
- Python version (`python --version`)
- Steps to reproduce the issue
- What you expected vs what actually happened

If you find a **security vulnerability** (especially anything related to credential handling or cookie storage), please do not open a public issue. Email the maintainer(jatinshihora0123@gmail.com) directly so it can be fixed before being disclosed to masses.

New here? Look for issues labeled [`good first issue`](https://github.com/Jatin-Shihora/leetshell/labels/good%20first%20issue) on GitHub.

## Pull Requests

### Before you start

- **Open an issue first.** Unless it's a trivial fix (typo, docs tweak), create an issue to discuss your idea before writing code. This saves everyone's time if the approach needs adjustment. Typo fixes, README improvements, and documentation corrections don't need a linked issue, just open the PR directly.
- **Keep PRs small and focused.** One PR should do one thing. If you're fixing a bug and also want to refactor something nearby, make two separate PRs. Large PRs that touch many unrelated things will likely be closed.
- **Link your PR to an issue.** If there's a related issue, reference it in your PR description.

### Setup

```bash
git clone https://github.com/Jatin-Shihora/leetshell.git
cd leetshell
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .
```

### Make your changes

```bash
git checkout -b my-feature
# make changes, test them...
```

### Test

Run the app and manually verify your changes work. If you're touching the TUI, actually open it and click around. Don't just assume it works.

```bash
leetshell
```

Run the test suite:

```bash
python -m pytest tests/
```

### PR description

Keep it short. A few lines explaining what you changed and why is plenty. Link the issue. That's it.

**Do not** write a two-page essay. Maintainers are humans with limited time, so respect that. If your change needs a super long explanation, that's a sign the PR might be too big.

A good PR description looks like:

```
Fixes #42

## What
Added difficulty filter cycling with the `d` key in problem list view.
Pressing `d` cycles through All → Easy → Medium → Hard → All.

## Why
Users currently have to scroll through the entire list to find problems
of a specific difficulty. This lets them filter without leaving the keyboard.

## Testing
- Tested on Windows Terminal and iTerm2
- Verified filter resets correctly when switching pages
- Works with search active
```

A bad PR description is 500 words of AI-generated filler explaining what a for-loop does.

### TUI changes? Show a screenshot

If your PR changes anything visual (layout, colors, new screens), include a screenshot or a short GIF in the PR description. Terminal UIs are hard to review from code alone.

### Commits

- Use imperative mood: "Add filter", not "Added filter" or "Adds filter"
- Keep the first line under 72 characters
- Prefix with a type: `fix:`, `feat:`, `docs:`, `refactor:`, `test:`, `chore:`

Good:
```
feat: add difficulty filter cycling with d key
fix: prevent crash when cache directory is missing
docs: fix typo in keybindings table
refactor: extract description rendering into helper
```

Bad:
```
Update code
Fixed stuff
Refactor code for improved maintainability and readability
```
- Don't bump version numbers in PRs, maintainers handle releases

### What makes a PR easy to review

- Small diff (under ~100 lines ideally)
- One logical change per PR
- Clear, short description
- You've actually tested it yourself
- No unrelated changes mixed in (reformatting, renaming, "improvements" to nearby code)

### What will get your PR closed

- Massive diffs with no prior discussion
- Unrelated changes bundled together
- Obvious signs of untested code
- No linked issue for non-trivial changes
- AI-generated slop (see below)

## Responsible use of AI

AI tools like Copilot, ChatGPT, Claude, etc. can be useful when writing code. But there are ground rules:

**You are responsible for every line you submit.** If you used AI to help write code, that's fine, but you must:

1. **Understand it.** If you can't explain what your code does line by line, don't submit it.
2. **Test it.** Actually run the app. Actually verify it works. "It compiled" is not testing.
3. **Review it yourself.** Read through the diff as if you were reviewing someone else's code. Remove anything unnecessary.

**Do not use AI to write your PR description.** We can tell. Write it yourself in your own words. A few honest sentences are worth more than a page of polished filler. Maintainers shouldn't have to wade through AI-generated walls of text to understand what your few line change does.

**Do not use AI to bulk-generate changes.** If your PR looks like you pointed an AI at the codebase and committed whatever it produced (reformatting files you didn't need to touch, adding docstrings everywhere, "improving" code that was fine), it will be closed. This isn't about being anti-AI, it's about respecting everyone's time.

**Signs of AI slop that will get your PR rejected:**
- Changes to files unrelated to the issue
- Unnecessary docstrings, comments, or type annotations added to code you didn't change
- Over-engineered abstractions for simple problems including unnecessary try-catch blocks or error handling that never happens
- PR descriptions longer than the actual code change
- Generic commit messages like "Refactor code for improved maintainability and readability"

In short: use AI as a tool, not as a replacement for thinking. If the code has your name on it, make sure you actually own it.

## Code style

- No strict linter enforced, but keep your code consistent with what's already there
- Use 4-space indentation
- Keep imports organized (stdlib, third-party, local)
- Don't add dependencies without discussion

## Project structure

```
src/leetshell/
  app.py              # Main app, event loop, screen management
  api/                # LeetCode API client, queries, caching
  models/             # Data models (problem, submission, user)
  tui/                # Terminal UI screens and components
```

If you're unsure where something belongs, check the existing code or ask in your issue.

## License

By contributing, you agree that your contributions will be licensed under the [GPL-3.0 License](LICENSE).
