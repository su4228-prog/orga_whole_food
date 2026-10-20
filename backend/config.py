"""설정 모음 — 비밀 열쇠는 .env 파일에서만 읽습니다 (코드에 직접 적지 않습니다)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent      # backend 폴더
SITE_DIR = BASE_DIR.parent                      # 사이트 폴더 (index.html 이 있는 곳)

load_dotenv(BASE_DIR / ".env")

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip()
SUPABASE_SERVICE_ROLE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
OPENAI_MODEL = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()

# 챗봇 사용 횟수 제한 (질문마다 OpenAI 요금이 나가므로)
CHAT_LIMIT_PER_USER = int(os.getenv("CHAT_LIMIT_PER_USER", "10"))          # 한 사람당
CHAT_LIMIT_WINDOW_SEC = int(os.getenv("CHAT_LIMIT_WINDOW_SEC", "600"))     # 이 시간(초) 동안
CHAT_LIMIT_PER_DAY = int(os.getenv("CHAT_LIMIT_PER_DAY", "300"))           # 사이트 전체 하루

# 화면(브라우저)에서 이 서버를 부를 수 있는 주소. 모든 곳("*")을 허용하지 않고 필요한 곳만 적습니다.
_DEFAULT_ORIGINS = ",".join([
    "http://localhost:8000", "http://127.0.0.1:8000",
    "http://localhost:8080", "http://127.0.0.1:8080",
    "http://localhost:5500", "http://127.0.0.1:5500",     # VS Code Live Server
    "http://localhost:5501", "http://127.0.0.1:5501",
    "https://su4228-prog.github.io",
])
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", _DEFAULT_ORIGINS).split(",") if o.strip()]
