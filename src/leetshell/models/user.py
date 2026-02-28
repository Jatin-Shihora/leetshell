from dataclasses import dataclass, field


@dataclass
class Credentials:
    leetcode_session: str = ""
    csrftoken: str = ""

    def is_valid(self) -> bool:
        return bool(self.leetcode_session and self.csrftoken)

    def to_dict(self) -> dict:
        return {
            "leetcode_session": self.leetcode_session,
            "csrftoken": self.csrftoken,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Credentials":
        return cls(
            leetcode_session=data.get("leetcode_session", ""),
            csrftoken=data.get("csrftoken", ""),
        )


@dataclass
class Preferences:
    language: str = "python3"

    def to_dict(self) -> dict:
        return {"language": self.language}

    @classmethod
    def from_dict(cls, data: dict) -> "Preferences":
        return cls(language=data.get("language", "python3"))


@dataclass
class UserConfig:
    credentials: Credentials = field(default_factory=Credentials)
    preferences: Preferences = field(default_factory=Preferences)

    def to_dict(self) -> dict:
        return {
            "credentials": self.credentials.to_dict(),
            "preferences": self.preferences.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UserConfig":
        return cls(
            credentials=Credentials.from_dict(data.get("credentials", {})),
            preferences=Preferences.from_dict(data.get("preferences", {})),
        )
