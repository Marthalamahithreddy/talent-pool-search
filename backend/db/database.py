# =============================================================
# FILE: backend/db/database.py
# PURPOSE: Supabase client singleton and helper to get a client
#          instance anywhere in the app without re-initializing.
#
# Usage:
#   from db.database import get_supabase
#   sb = get_supabase()
#   sb.table("candidates").select("*").execute()
# =============================================================

import os
from functools import lru_cache

import httpx
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """Return a cached Supabase client built from env vars.

    lru_cache(maxsize=1) ensures we create the client exactly once
    per process, which is what Supabase recommends.
    """
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    if not url or not key:
        raise EnvironmentError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env"
        )

    client = create_client(url, key)
    _force_http1(client)
    return client


def _force_http1(client: Client) -> None:
    """Rebuild the PostgREST httpx session without HTTP/2.

    postgrest-py hard-codes ``http2=True``. Combined with httpcore 1.0.x
    this intermittently raises:
        httpx.LocalProtocolError: Received pseudo-header in trailer
    which surfaces as random 500s on DB reads/writes. HTTP/1.1 is just as
    fast for our small JSON payloads and avoids the bug entirely.
    """
    pg = client.postgrest
    old = pg.session
    pg.session = httpx.Client(
        base_url=old.base_url,
        headers=old.headers,
        timeout=old.timeout,
        follow_redirects=True,
        http2=False,
    )
