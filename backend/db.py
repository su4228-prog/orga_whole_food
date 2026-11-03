"""Supabase 연결 — 작업 스레드마다 연결을 하나씩 만들어 재사용합니다.

서버는 요청을 여러 스레드에서 동시에 처리합니다(메인 페이지는 섹션 6개를 한꺼번에 요청).
연결 하나를 여러 스레드가 함께 쓰면 가끔 통신이 엉켜 요청이 실패하므로, 스레드별로 따로 둡니다.
"""
import threading

from supabase import Client, create_client

from config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL

_local = threading.local()


def get_client() -> Client:
    client = getattr(_local, "client", None)
    if client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError("Supabase 설정이 비어 있습니다. backend/.env 를 확인하세요.")
        client = _local.client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return client
