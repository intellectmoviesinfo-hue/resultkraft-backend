"""
FastAPI JWT verification using Supabase tokens.
Every protected endpoint must use: user = Depends(get_current_user)
"""
import os
import jwt
from functools import lru_cache
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from jwt import PyJWKClient

bearer_scheme = HTTPBearer()

@lru_cache
def _get_jwks_client() -> PyJWKClient:
    supabase_url = os.getenv("SUPABASE_URL", "")
    if not supabase_url:
        raise RuntimeError("SUPABASE_URL environment variable not set")
    return PyJWKClient(f"{supabase_url}/auth/v1/.well-known/jwks.json")


def _get_supabase_url() -> str:
    return os.getenv("SUPABASE_URL", "")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    token = credentials.credentials
    try:
        jwks_client = _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        supabase_url = _get_supabase_url()

        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience="authenticated",
            issuer=f"{supabase_url}/auth/v1",
            options={"verify_exp": True},
        )

        if not payload.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
            )
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_user_id(user: dict = Depends(get_current_user)) -> str:
    return user["sub"]
