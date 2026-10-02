from sqlalchemy.engine import make_url


def asyncpg_compatible_url(database_url: str) -> str:
    url = make_url(database_url)
    query = dict(url.query)
    query.pop("channel_binding", None)
    sslmode = query.pop("sslmode", None)
    if sslmode is not None:
        query.setdefault("ssl", sslmode)
    return url.set(query=query).render_as_string(hide_password=False)
