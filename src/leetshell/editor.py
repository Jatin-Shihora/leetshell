from pathlib import Path

from leetshell.constants import LANGUAGE_EXTENSIONS, SOLUTIONS_DIR


def get_solution_path(title_slug: str, lang_slug: str) -> Path:
    """Get a persistent path for a solution file."""
    ext = LANGUAGE_EXTENSIONS.get(lang_slug, ".txt")
    SOLUTIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SOLUTIONS_DIR / f"{title_slug}{ext}"
