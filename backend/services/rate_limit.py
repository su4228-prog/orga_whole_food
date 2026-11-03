"""사용 횟수 제한 — 상담봇 · 사진 검색 · 로그인 · 가입 · 관리자 AI 분석에 공통으로 씁니다.
(상담봇 질문마다 OpenAI 요금이, 사진 검색마다 서버 CPU 가 쓰이므로 남용을 막습니다.)

- 한 사람(접속 주소)당: 정해진 시간 안에 N번까지
- 사이트 전체: 하루 N번까지
횟수는 Supabase(rate_limit_hit 함수, sql/005_rate_limit_and_photo.sql)에 기록해 서버가 다시 켜져도 유지됩니다.
DB 기록을 쓸 수 없으면 서버 메모리로 대신 셉니다.
"""
import logging
import time
from collections import defaultdict, deque
from threading import Lock

from db import get_client

log = logging.getLogger("olga.rate_limit")


class RateLimitExceeded(Exception):
    """제한을 넘었을 때 — 메시지는 그대로 사용자에게 보여줍니다."""


DAY_MESSAGE = "오늘 이용 가능 횟수를 모두 사용했어요. 내일 다시 이용해 주세요."


def _user_message(wait_sec: float) -> str:
    return f"요청이 너무 많아요. 약 {max(1, int(wait_sec // 60) + 1)}분 뒤에 다시 시도해 주세요."


class RateLimiter:
    def __init__(self, bucket: str, per_user: int, window_sec: int, per_day: int):
        self.bucket = bucket
        self.per_user = per_user
        self.window = window_sec
        self.per_day = per_day
        self._hits: dict[str, deque] = defaultdict(deque)
        self._day = ""
        self._day_count = 0
        self._lock = Lock()

    def check(self, user_key: str) -> None:
        """통과하면 1번 기록하고, 넘었으면 RateLimitExceeded"""
        try:
            result = get_client().rpc("rate_limit_hit", {
                "p_bucket": self.bucket, "p_key": user_key, "p_window_sec": self.window,
                "p_per_user": self.per_user, "p_per_day": self.per_day}).execute().data
        except Exception as e:                       # 함수가 아직 없거나 DB 오류 → 메모리로 대신
            log.warning("횟수 기록을 DB 에 남기지 못해 메모리로 셉니다: %s", e)
            return self._check_memory(user_key)
        if result == "day":
            raise RateLimitExceeded(DAY_MESSAGE)
        if isinstance(result, str) and result.startswith("user:"):
            raise RateLimitExceeded(_user_message(float(result.split(":", 1)[1])))

    def _check_memory(self, user_key: str) -> None:
        now = time.time()
        today = time.strftime("%Y-%m-%d")
        with self._lock:
            if today != self._day:                   # 날짜가 바뀌면 전체 횟수 초기화
                self._day, self._day_count = today, 0
            if self._day_count >= self.per_day:
                raise RateLimitExceeded(DAY_MESSAGE)
            q = self._hits[user_key]
            while q and now - q[0] > self.window:    # 시간이 지난 기록은 버림
                q.popleft()
            if len(q) >= self.per_user:
                raise RateLimitExceeded(_user_message(self.window - (now - q[0])))
            q.append(now)
            self._day_count += 1
