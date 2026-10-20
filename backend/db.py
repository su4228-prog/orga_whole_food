"""보관함(Supabase) 연결 — 한 번만 만들어 계속 재사용합니다."""
from functools import lru_cache

from supabase import Client, create_client

from config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL


@lru_cache(maxsize=1)
def get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Supabase 설정이 비어 있습니다. backend/.env 를 확인하세요.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
