import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientError

from agent_platform.config import get_settings

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    subject: str
    username: str | None
    roles: frozenset[str]
    groups: tuple[str, ...]
    claims: dict[str, Any]


@lru_cache(maxsize=8)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True, timeout=5)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="A valid Keycloak access token is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    settings = get_settings()
    if not credentials or not settings.oidc_issuer_url or not settings.oidc_audience:
        raise _unauthorized()

    issuer = settings.oidc_issuer_url.rstrip("/")
    jwks_url = settings.oidc_jwks_url or f"{issuer}/protocol/openid-connect/certs"
    try:
        claims = await asyncio.to_thread(
            _decode_access_token,
            credentials.credentials,
            jwks_url,
            settings.oidc_audience,
            issuer,
        )
    except (jwt.PyJWTError, PyJWKClientError, ValueError) as error:
        raise _unauthorized() from error

    realm_access = claims.get("realm_access", {})
    realm_roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else []
    client_roles = claims.get("resource_access", {})
    roles = {role for role in realm_roles if isinstance(role, str)} if isinstance(
        realm_roles, list
    ) else set()
    if isinstance(client_roles, dict):
        for client in client_roles.values():
            if isinstance(client, dict) and isinstance(client.get("roles"), list):
                roles.update(client["roles"])
    groups_value = claims.get(settings.oidc_groups_claim, [])
    groups = tuple(group for group in groups_value if isinstance(group, str)) if isinstance(
        groups_value, list
    ) else ()
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise _unauthorized()
    username = claims.get("preferred_username")
    return Principal(
        subject,
        username if isinstance(username, str) else None,
        frozenset(roles),
        groups,
        claims,
    )


def _decode_access_token(token: str, jwks_url: str, audience: str, issuer: str) -> dict[str, Any]:
    signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=audience,
        issuer=issuer,
        options={"require": ["exp", "iat", "iss", "sub", "aud"]},
    )


def require_role(role: str) -> Callable[..., Awaitable[Principal]]:
    async def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if role not in principal.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Required role is missing.",
            )
        return principal

    return dependency
