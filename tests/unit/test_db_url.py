from agent_platform.db_url import asyncpg_compatible_url


def test_asyncpg_url_drops_libpq_channel_binding_and_maps_sslmode() -> None:
    url = asyncpg_compatible_url(
        "postgresql+asyncpg://user:password@db.example/agent"
        "?sslmode=require&channel_binding=require"
    )

    assert url == "postgresql+asyncpg://user:password@db.example/agent?ssl=require"


def test_asyncpg_url_preserves_explicit_ssl_setting() -> None:
    url = asyncpg_compatible_url(
        "postgresql+asyncpg://user:password@db.example/agent"
        "?ssl=verify-full&sslmode=require&channel_binding=require"
    )

    assert url == "postgresql+asyncpg://user:password@db.example/agent?ssl=verify-full"
