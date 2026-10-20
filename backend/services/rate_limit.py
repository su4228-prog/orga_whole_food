"""챗봇 남용 막기 — 질문마다 OpenAI 요금이 나가므로 사용 횟수를 제한합니다.

- 한 사람(접속 주소)당: 정해진 시간 안에 N번까지
- 사이트 전체: 하루 N번까지
서버 메모리에 기록하므로 서버를 다시 켜면 횟수가 초기화됩니다. (서버 1대 기준)
"""
import time
from collections import defaultdict, deque
from threading import Lock


class RateLimitExceeded(Exception):
    """제한을 넘었을 때 — 메시지는 그대로 사용자에게 보여줍니다."""


class ChatRateLimiter:
    def __init__(self, per_user: int, window_sec: int, per_day: int):
        self.per_user = per_user
        self.window = window_sec
        self.per_day = per_day
        self._hits: dict[str, deque] = defaultdict(deque)
        self._day = ""
        self._day_count = 0
        self._lock = Lock()

    def check(self, user_key: str) -> None:
        now = time.time()
        today = time.strftime("%Y-%m-%d")
        with self._lock:
            if today != self._day:                       # 날짜가 바뀌면 전체 횟수 초기화
                self._day, self._day_count = today, 0
            if self._day_count >= self.per_day:
                raise RateLimitExceeded("오늘 상담 가능 횟수를 모두 사용했어요. 내일 다시 이용해 주세요.")
            q = self._hits[user_key]
            while q and now - q[0] > self.window:        # 시간이 지난 기록은 버림
                q.popleft()
            if len(q) >= self.per_user:
                wait_min = max(1, int((self.window - (now - q[0])) // 60) + 1)
                raise RateLimitExceeded(f"질문이 너무 많아요. 약 {wait_min}분 뒤에 다시 물어봐 주세요.")
            q.append(now)
            self._day_count += 1
