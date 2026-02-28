from dataclasses import dataclass, field


@dataclass
class ProblemSummary:
    frontend_id: str = ""
    title: str = ""
    title_slug: str = ""
    difficulty: str = ""
    ac_rate: float = 0.0
    paid_only: bool = False
    status: str | None = None  # "ac", "notac", or None
    topic_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "frontend_id": self.frontend_id,
            "title": self.title,
            "title_slug": self.title_slug,
            "difficulty": self.difficulty,
            "ac_rate": self.ac_rate,
            "paid_only": self.paid_only,
            "status": self.status,
            "topic_tags": self.topic_tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProblemSummary":
        return cls(
            frontend_id=str(data.get("frontend_id", data.get("frontendQuestionId", ""))),
            title=data.get("title", ""),
            title_slug=data.get("title_slug", data.get("titleSlug", "")),
            difficulty=data.get("difficulty", ""),
            ac_rate=float(data.get("ac_rate", data.get("acRate", 0.0))),
            paid_only=data.get("paid_only", data.get("paidOnly", False)),
            status=data.get("status"),
            topic_tags=data.get("topic_tags", []),
        )

    @classmethod
    def from_api(cls, data: dict) -> "ProblemSummary":
        tags = [t["name"] for t in data.get("topicTags", [])]
        return cls(
            frontend_id=str(data.get("frontendQuestionId", "")),
            title=data.get("title", ""),
            title_slug=data.get("titleSlug", ""),
            difficulty=data.get("difficulty", ""),
            ac_rate=float(data.get("acRate", 0.0)),
            paid_only=data.get("paidOnly", False),
            status=data.get("status"),
            topic_tags=tags,
        )


@dataclass
class CodeSnippet:
    lang: str = ""
    lang_slug: str = ""
    code: str = ""

    def to_dict(self) -> dict:
        return {"lang": self.lang, "lang_slug": self.lang_slug, "code": self.code}

    @classmethod
    def from_dict(cls, data: dict) -> "CodeSnippet":
        return cls(
            lang=data.get("lang", ""),
            lang_slug=data.get("lang_slug", data.get("langSlug", "")),
            code=data.get("code", ""),
        )


@dataclass
class ProblemDetail:
    question_id: str = ""
    frontend_id: str = ""
    title: str = ""
    title_slug: str = ""
    content: str = ""  # HTML content
    difficulty: str = ""
    example_testcases: list[str] = field(default_factory=list)
    code_snippets: list[CodeSnippet] = field(default_factory=list)
    topic_tags: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    stats: str = ""
    paid_only: bool = False

    def get_snippet(self, lang_slug: str) -> CodeSnippet | None:
        for s in self.code_snippets:
            if s.lang_slug == lang_slug:
                return s
        return None

    def to_dict(self) -> dict:
        return {
            "question_id": self.question_id,
            "frontend_id": self.frontend_id,
            "title": self.title,
            "title_slug": self.title_slug,
            "content": self.content,
            "difficulty": self.difficulty,
            "example_testcases": self.example_testcases,
            "code_snippets": [s.to_dict() for s in self.code_snippets],
            "topic_tags": self.topic_tags,
            "hints": self.hints,
            "stats": self.stats,
            "paid_only": self.paid_only,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProblemDetail":
        snippets = [CodeSnippet.from_dict(s) for s in data.get("code_snippets", [])]
        return cls(
            question_id=data.get("question_id", ""),
            frontend_id=data.get("frontend_id", ""),
            title=data.get("title", ""),
            title_slug=data.get("title_slug", ""),
            content=data.get("content", ""),
            difficulty=data.get("difficulty", ""),
            example_testcases=data.get("example_testcases", []),
            code_snippets=snippets,
            topic_tags=data.get("topic_tags", []),
            hints=data.get("hints", []),
            stats=data.get("stats", ""),
            paid_only=data.get("paid_only", False),
        )

    @classmethod
    def from_api(cls, data: dict) -> "ProblemDetail":
        tags = [t["name"] for t in data.get("topicTags", [])]
        snippets = [CodeSnippet.from_dict(s) for s in data.get("codeSnippets", []) or []]
        testcases = data.get("exampleTestcaseList", []) or []
        return cls(
            question_id=data.get("questionId", ""),
            frontend_id=data.get("questionFrontendId", ""),
            title=data.get("title", ""),
            title_slug=data.get("titleSlug", ""),
            content=data.get("content", ""),
            difficulty=data.get("difficulty", ""),
            example_testcases=testcases,
            code_snippets=snippets,
            topic_tags=tags,
            hints=data.get("hints", []) or [],
            stats=data.get("stats", ""),
            paid_only=data.get("isPaidOnly", False),
        )
