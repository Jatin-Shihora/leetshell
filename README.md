
# leetshell

```
  _                _    ____          _
 | |    ___   ___ | |_ / ___|___   __| | ___
 | |   / _ \ / _ \| __| |   / _ \ / _` |/ _ \
 | |__|  __/|  __/| |_| |__| (_) | (_| |  __/
 |_____\___| \___| \__|\____\___/ \__,_|\___|
      ____  _   _ _____ _     _
     / ___|| | | | ____| |   | |
     \___ \| |_| |  _| | |   | |
      ___) |  _  | |___| |___| |___
     |____/|_| |_|_____|_____|_____|
```

Solve LeetCode problems without leaving your terminal.

Browse problems, read descriptions, write code with syntax highlighting, test against sample cases, and submit - all from a single TUI.

https://github.com/user-attachments/assets/REPLACE_WITH_UPLOADED_VIDEO_URL

## Install

```bash
pip install leetshell
```

Or from source:

```bash
git clone https://github.com/Jatin-Shihora/leetshell.git
cd leetshell
pip install -e .
```

## Usage

```bash
leetshell
```

## Features

- **Split view** - description on the left, code editor on the right (like the LeetCode website)
- **Built-in code editor** - syntax highlighting via Pygments, cursor movement, selection, undo/redo
- **19 languages** - C++, Python, Java, JavaScript, Rust, Go, Kotlin, and more
- **Test & submit** - run against sample cases or submit directly, results shown inline
- **Browser login** - auto-extracts session cookies from Chrome, Edge, Brave, Arc
- **Offline cache** - problem list and details are cached locally for fast navigation
- **Solutions persist** - your code is saved locally and restored when you revisit a problem

## Login

On first launch you'll see the login screen:

### Login via Browser (recommended)

1. Select **Login via Browser**
2. Pick your browser (Edge, Chrome, Arc, Brave)
3. Log in to LeetCode in the browser window that opens
4. Come back to the terminal - session is detected automatically

Your session is saved locally. You won't need to log in again until it expires.

### Manual Cookie Entry

1. Select **Manual Cookie Entry**
2. Open [leetcode.com](https://leetcode.com) and log in
3. Open DevTools (`F12`) > **Application** > **Cookies** > `https://leetcode.com`
4. Copy `LEETCODE_SESSION` and `csrftoken` values
5. Paste them into the app

## Keybindings

### Problem List

| Key | Action |
|-----|--------|
| `j` / `k` or arrows | Scroll up/down |
| `Enter` | Open problem |
| `/` | Search by title |
| `d` | Cycle difficulty filter (All/Easy/Medium/Hard) |
| `r` | Refresh list |
| `PgUp` / `PgDn` | Navigate pages |
| `L` | Logout |
| `Esc` / `q` | Quit |

### Problem Detail (Split View)

| Key | Action |
|-----|--------|
| `Ctrl+D` | Cycle view: split > editor > description > split |
| `Ctrl+T` | Test against sample cases |
| `Ctrl+S` | Submit solution |
| `Ctrl+L` | Cycle language |
| `Ctrl+U` | Undo |
| `Ctrl+R` | Redo |
| `Ctrl+Up/Down` | Scroll description pane |
| `Shift+Arrows` | Select text |
| `Ctrl+Left/Right` | Word movement |
| `Esc` | Back to problem list |

### Code Editor

| Key | Action |
|-----|--------|
| Arrow keys | Move cursor |
| `Shift+Arrows` | Select characters/lines |
| `Ctrl+Left/Right` | Jump by word |
| `Ctrl+Shift+Left/Right` | Select by word |
| `Home` / `End` | Start/end of line |
| `PgUp` / `PgDn` | Page up/down |
| `Tab` | Insert 4 spaces |
| `Backspace` / `Delete` | Delete (selection-aware) |

## View Modes

**Split** (default) - description on the left (~40%), code editor on the right (~60%), separated by a vertical divider.

**Editor** - full-screen code editor with language header.

**Description** - full-screen problem description with scroll.

Cycle between them with `Ctrl+D`.

## Configuration

Everything is stored in `~/.leetshell/`:

```
~/.leetshell/
  config.json       # credentials + preferences (language choice)
  cache/            # cached problem list and details (auto-expires)
  solutions/        # your solution files (persistent)
  debug.log         # debug log for troubleshooting
```

## Requirements

- Python 3.10+
- A terminal with color support (Windows Terminal, iTerm2, most modern terminals)

## Tech Stack

- **blessed** - terminal rendering and keyboard input
- **pygments** - syntax highlighting for 19 languages
- **httpx** - async HTTP client for LeetCode API
- **html2text** - HTML to text conversion for problem descriptions
- **websockets** - real-time submission result polling
- **cryptography** - browser cookie decryption

No frameworks - the TUI is built from scratch using direct ANSI escape codes and a custom screen/component architecture.

## Project Structure

```
src/leetshell/
  app.py                  # Main app, event loop, screen management
  browser_cookies.py      # Browser cookie extraction (Chrome DevTools Protocol)
  config.py               # Load/save config
  constants.py            # URLs, language map, status codes
  editor.py               # External editor integration
  api/
    client.py             # HTTP client with rate limiting + retries
    queries.py            # GraphQL queries
    auth.py               # Session validation
    cache.py              # File-based response cache
    problems.py           # Problem list + detail fetching
    submissions.py        # Submit + test + result polling
  models/
    problem.py            # ProblemSummary, ProblemDetail
    submission.py         # TestResult, SubmissionResult
    user.py               # Credentials, Preferences, UserConfig
  tui/
    core.py               # Screen base class, terminal helpers
    login.py              # Login screen with ASCII art
    problem_list.py       # Problem browser with filters + search
    problem_detail.py     # Split/editor/desc views, key routing
    editor.py             # Built-in code editor with syntax highlighting
    test_result.py        # Test case results display
    submission_result.py  # Submission verdict display
```

## License

GPL-3.0 - see [LICENSE](LICENSE) for details.
