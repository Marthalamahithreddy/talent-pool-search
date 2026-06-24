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

    return create_client(url, key)
