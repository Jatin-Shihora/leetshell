import os
from pathlib import Path

# LeetCode URLs
LEETCODE_BASE_URL = "https://leetcode.com"
LEETCODE_GRAPHQL_URL = f"{LEETCODE_BASE_URL}/graphql"
LEETCODE_SUBMIT_URL = f"{LEETCODE_BASE_URL}/problems/{{slug}}/submit/"
LEETCODE_INTERPRET_URL = f"{LEETCODE_BASE_URL}/problems/{{slug}}/interpret_solution/"
LEETCODE_CHECK_URL = f"{LEETCODE_BASE_URL}/submissions/detail/{{id}}/check/"

# Config paths
CONFIG_DIR = Path(os.path.expanduser("~")) / ".leetshell"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_DIR = CONFIG_DIR / "cache"
SOLUTIONS_DIR = CONFIG_DIR / "solutions"

# Cache TTLs (seconds)
PROBLEM_LIST_CACHE_TTL = 3600       # 1 hour
PROBLEM_DETAIL_CACHE_TTL = 86400    # 24 hours

# API settings
RATE_LIMIT_INTERVAL = 1.0  # seconds between requests
MAX_RETRIES = 4
POLL_INTERVAL = 1.5  # seconds between poll requests
POLL_TIMEOUT = 30.0  # max seconds to poll

# Language map: display name -> slug
LANGUAGE_MAP = {
    "C++": "cpp",
    "Java": "java",
    "Python3": "python3",
    "Python": "python",
    "JavaScript": "javascript",
    "TypeScript": "typescript",
    "C#": "csharp",
    "C": "c",
    "Go": "golang",
    "Kotlin": "kotlin",
    "Swift": "swift",
    "Rust": "rust",
    "Ruby": "ruby",
    "PHP": "php",
    "Dart": "dart",
    "Scala": "scala",
    "Elixir": "elixir",
    "Erlang": "erlang",
    "Racket": "racket",
}

# Reverse map: slug -> display name
SLUG_TO_LANGUAGE = {v: k for k, v in LANGUAGE_MAP.items()}

# File extensions per language slug
LANGUAGE_EXTENSIONS = {
    "cpp": ".cpp",
    "java": ".java",
    "python3": ".py",
    "python": ".py",
    "javascript": ".js",
    "typescript": ".ts",
    "csharp": ".cs",
    "c": ".c",
    "golang": ".go",
    "kotlin": ".kt",
    "swift": ".swift",
    "rust": ".rs",
    "ruby": ".rb",
    "php": ".php",
    "dart": ".dart",
    "scala": ".scala",
    "elixir": ".ex",
    "erlang": ".erl",
    "racket": ".rkt",
}

# Difficulty display
DIFFICULTY_COLORS = {
    "Easy": "green",
    "Medium": "yellow",
    "Hard": "red",
}

# Submission status codes
STATUS_ACCEPTED = 10
STATUS_WRONG_ANSWER = 11
STATUS_TLE = 14
STATUS_RUNTIME_ERROR = 15
STATUS_COMPILE_ERROR = 20

STATUS_MESSAGES = {
    STATUS_ACCEPTED: "Accepted",
    STATUS_WRONG_ANSWER: "Wrong Answer",
    STATUS_TLE: "Time Limit Exceeded",
    STATUS_RUNTIME_ERROR: "Runtime Error",
    STATUS_COMPILE_ERROR: "Compile Error",
}

STATUS_COLORS = {
    STATUS_ACCEPTED: "green",
    STATUS_WRONG_ANSWER: "red",
    STATUS_TLE: "red",
    STATUS_RUNTIME_ERROR: "red",
    STATUS_COMPILE_ERROR: "red",
}

# Language slug -> Pygments lexer name for syntax highlighting
LANG_SLUG_TO_PYGMENTS = {
    "python3": "python",
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "java": "java",
    "cpp": "cpp",
    "c": "c",
    "golang": "go",
    "rust": "rust",
    "kotlin": "kotlin",
    "swift": "swift",
    "ruby": "ruby",
    "scala": "scala",
    "csharp": "csharp",
    "php": "php",
    "dart": "dart",
    "elixir": "elixir",
    "erlang": "erlang",
    "racket": "racket",
}
