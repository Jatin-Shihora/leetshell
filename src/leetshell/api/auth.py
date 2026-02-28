from leetshell.api.client import LeetCodeClient, AuthenticationError, NetworkError
from leetshell.api.queries import USER_STATUS_QUERY


async def validate_session(client: LeetCodeClient) -> str | None:
    """Validate session and return username if valid, None otherwise.

    Returns None only when the server explicitly says the session is invalid.
    Raises on network errors so the caller can decide what to do.
    """
    try:
        data = await client.graphql(USER_STATUS_QUERY)
        user_status = data.get("userStatus", {})
        if user_status.get("isSignedIn"):
            return user_status.get("username", "")
        return None
    except AuthenticationError:
        return None
