"""Auth disabled for the demo.

Protected endpoints used to verify the Supabase JWT here. For the demo, auth
is removed entirely: every request is accepted as the "demo_user" identity,
which is also where demo enrollments are stored and matched against.
"""
from fastapi import Header


async def verify_token(authorization: str | None = Header(None)) -> str:
    """No-op auth dependency - accept any request as 'demo_user'."""
    return "demo_user"
