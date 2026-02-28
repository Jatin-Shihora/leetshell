import json

from leetshell.constants import CONFIG_DIR, CONFIG_FILE
from leetshell.models.user import UserConfig


def load_config() -> UserConfig:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return UserConfig.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return UserConfig()
    return UserConfig()


def save_config(config: UserConfig) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(config.to_dict(), indent=2),
        encoding="utf-8",
    )
