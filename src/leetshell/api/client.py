import asyncio
import time

import httpx

from leetshell.constants import LEETCODE_BASE_URL, MAX_RETRIES, RATE_LIMIT_INTERVAL


class LeetCodeError(Exception):
    pass


class AuthenticationError(LeetCodeError):
    pass


class RateLimitError(LeetCodeError):
    pass


class NetworkError(LeetCodeError):
    pass


class LeetCodeClient:
    def __init__(self, leetcode_session: str = "", csrftoken: str = ""):
        self._session = leetcode_session
        self._csrf = csrftoken
        self._lock = asyncio.Lock()
        self._last_request_time = 0.0
        self._client: httpx.AsyncClient | None = None

    def update_credentials(self, leetcode_session: str, csrftoken: str):
        self._session = leetcode_session
        self._csrf = csrftoken
        # Recreate client on next request
        if self._client:
            # Schedule close but don't await here
            self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=LEETCODE_BASE_URL,
                headers={
                    "Content-Type": "application/json",
                    "Referer": LEETCODE_BASE_URL,
                    "x-csrftoken": self._csrf,
                },
                cookies={
                    "LEETCODE_SESSION": self._session,
                    "csrftoken": self._csrf,
                },
                timeout=30.0,
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                    keepalive_expiry=30,
                ),
                http2=False,
            )
        return self._client

    async def _rate_limit(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < RATE_LIMIT_INTERVAL:
                await asyncio.sleep(RATE_LIMIT_INTERVAL - elapsed)
            self._last_request_time = time.monotonic()

    async def graphql(self, query: str, variables: dict | None = None) -> dict:
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        data = await self._request("POST", "/graphql", json=payload)
        if "errors" in data:
            raise LeetCodeError(data["errors"][0].get("message", "GraphQL error"))
        return data.get("data", {})

    async def post(self, path: str, json: dict | None = None) -> dict:
        return await self._request("POST", path, json=json)

    async def get(self, path: str) -> dict:
        return await self._request("GET", path)

    async def _request(
        self, method: str, path: str, json: dict | None = None
    ) -> dict:
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            await self._rate_limit()
            try:
                client = await self._get_client()
                response = await client.request(method, path, json=json)

                if response.status_code == 401 or response.status_code == 403:
                    raise AuthenticationError("Session expired or invalid")
                if response.status_code == 429:
                    if attempt < MAX_RETRIES:
                        wait = 2 ** attempt
                        await asyncio.sleep(wait)
                        continue
                    raise RateLimitError("Rate limited by LeetCode")
                if response.status_code >= 500:
                    if attempt < MAX_RETRIES:
                        wait = 2 ** attempt
                        await asyncio.sleep(wait)
                        continue
                    raise NetworkError(f"Server error: {response.status_code}")

                response.raise_for_status()
                return response.json()

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    wait = 2 ** attempt
                    await asyncio.sleep(wait)
                    continue
                raise NetworkError(f"Network error: {e}") from e
            except (AuthenticationError, RateLimitError):
                raise
            except httpx.HTTPStatusError as e:
                raise LeetCodeError(f"HTTP error: {e.response.status_code}") from e

        raise NetworkError(f"Request failed after {MAX_RETRIES} retries: {last_error}")

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
