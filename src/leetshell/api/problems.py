from leetshell.api.client import LeetCodeClient
from leetshell.api.queries import PROBLEM_LIST_QUERY, QUESTION_DETAIL_QUERY
from leetshell.api.cache import get_cached, set_cached
from leetshell.constants import PROBLEM_LIST_CACHE_TTL, PROBLEM_DETAIL_CACHE_TTL
from leetshell.models.problem import ProblemSummary, ProblemDetail


class ProblemService:
    def __init__(self, client: LeetCodeClient):
        self._client = client

    async def get_problem_list(
        self,
        limit: int = 50,
        skip: int = 0,
        difficulty: str = "",
        tags: list[str] | None = None,
        search: str = "",
    ) -> tuple[list[ProblemSummary], int]:
        """Fetch problem list. Returns (problems, total_count)."""
        filters: dict = {}
        if difficulty:
            filters["difficulty"] = difficulty.upper()
        if tags:
            filters["tags"] = tags
        if search:
            filters["searchKeywords"] = search

        cache_key = f"problems_{limit}_{skip}_{difficulty}_{search}_{'_'.join(tags or [])}"
        cached = get_cached(cache_key, PROBLEM_LIST_CACHE_TTL)
        if cached:
            problems = [ProblemSummary.from_dict(p) for p in cached["questions"]]
            return problems, cached["total"]

        variables = {
            "categorySlug": "",
            "limit": limit,
            "skip": skip,
            "filters": filters,
        }
        data = await self._client.graphql(PROBLEM_LIST_QUERY, variables)
        result = data.get("problemsetQuestionList", {})
        total = result.get("total", 0)
        questions_data = result.get("questions", [])

        problems = [ProblemSummary.from_api(q) for q in questions_data]

        # Cache the raw data
        set_cached(cache_key, {
            "total": total,
            "questions": [p.to_dict() for p in problems],
        })

        return problems, total

    async def get_problem_detail(self, title_slug: str) -> ProblemDetail:
        """Fetch full problem details."""
        cache_key = f"detail_{title_slug}"
        cached = get_cached(cache_key, PROBLEM_DETAIL_CACHE_TTL)
        if cached:
            return ProblemDetail.from_dict(cached)

        data = await self._client.graphql(
            QUESTION_DETAIL_QUERY,
            {"titleSlug": title_slug},
        )
        question = data.get("question", {})
        detail = ProblemDetail.from_api(question)

        set_cached(cache_key, detail.to_dict())
        return detail
