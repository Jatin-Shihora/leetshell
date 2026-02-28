import asyncio

from leetshell.api.client import LeetCodeClient, LeetCodeError
from leetshell.constants import (
    LEETCODE_CHECK_URL,
    LEETCODE_INTERPRET_URL,
    LEETCODE_SUBMIT_URL,
    POLL_INTERVAL,
    POLL_TIMEOUT,
)
from leetshell.models.submission import SubmissionResult, TestResult


class SubmissionService:
    def __init__(self, client: LeetCodeClient):
        self._client = client

    async def submit(
        self,
        title_slug: str,
        question_id: str,
        lang: str,
        code: str,
    ) -> SubmissionResult:
        """Submit solution and poll for result."""
        path = LEETCODE_SUBMIT_URL.format(slug=title_slug)
        # path is a full URL, we need just the path portion
        path = path.replace("https://leetcode.com", "")
        payload = {
            "question_id": question_id,
            "lang": lang,
            "typed_code": code,
        }
        resp = await self._client.post(path, json=payload)
        submission_id = resp.get("submission_id")
        if not submission_id:
            raise LeetCodeError("No submission_id in response")

        data = await self._poll_result(submission_id)
        return SubmissionResult.from_api(data)

    async def test(
        self,
        title_slug: str,
        question_id: str,
        lang: str,
        code: str,
        test_input: str,
    ) -> TestResult:
        """Test solution against sample cases and poll for result."""
        path = LEETCODE_INTERPRET_URL.format(slug=title_slug)
        path = path.replace("https://leetcode.com", "")
        payload = {
            "question_id": question_id,
            "lang": lang,
            "typed_code": code,
            "data_input": test_input,
        }
        resp = await self._client.post(path, json=payload)
        interpret_id = resp.get("interpret_id")
        if not interpret_id:
            raise LeetCodeError("No interpret_id in response")

        data = await self._poll_result(interpret_id)
        return TestResult.from_api(data, input_data=test_input)

    async def _poll_result(self, submission_id: str | int) -> dict:
        """Poll check endpoint until result is ready."""
        check_path = LEETCODE_CHECK_URL.format(id=submission_id)
        check_path = check_path.replace("https://leetcode.com", "")
        elapsed = 0.0
        while elapsed < POLL_TIMEOUT:
            data = await self._client.get(check_path)
            state = data.get("state")
            if state and state != "PENDING" and state != "STARTED":
                return data
            await asyncio.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL

        raise LeetCodeError("Timed out waiting for submission result")
