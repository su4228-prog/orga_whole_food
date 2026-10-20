"""Supabase 연결 시험 — 키 값은 화면에 출력하지 않고, 성공/실패와 표 상태만 보여줍니다.

실행:  backend 폴더에서  .venv\\Scripts\\python scripts\\check_connection.py
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

url = (os.getenv("SUPABASE_URL") or "").strip()
key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()

print("1) .env 값 확인")
print("   SUPABASE_URL              :", "입력됨" if url else "비어 있음")
print("   SUPABASE_SERVICE_ROLE_KEY :", "입력됨" if key else "비어 있음")
if not url or not key:
    sys.exit("→ .env 에 빈 값이 있습니다.")

problems = []
if not url.startswith("https://") or ".supabase.co" not in url:
    problems.append("주소는 https://글자.supabase.co 모양이어야 합니다.")
if key.startswith("sb_publishable_"):
    problems.append("Publishable 키가 들어 있습니다. Secret 키(sb_secret_…)를 넣어야 합니다.")
if " " in url or " " in key or '"' in url or '"' in key or "'" in key:
    problems.append("값에 공백이나 따옴표가 들어 있습니다.")
for p in problems:
    print("   ⚠", p)
if problems:
    sys.exit("→ 위 문제를 고친 뒤 다시 시험하세요.")

from supabase import create_client  # noqa: E402

print("2) 보관함 접속")
client = create_client(url, key)
print("   접속 객체 생성: 성공")

print("3) 표 4개 확인")
ok = True
for table in ("products", "sections", "section_products", "product_details"):
    try:
        res = client.table(table).select("*", count="exact").limit(1).execute()
        print(f"   {table:18} 있음 · 현재 {res.count}줄")
    except Exception as e:  # noqa: BLE001
        ok = False
        msg = str(e)
        for secret in (key,):
            msg = msg.replace(secret, "***")
        print(f"   {table:18} 실패 → {msg[:160]}")
print("결과:", "연결 성공 ✅" if ok else "연결은 됐지만 표 접근에 문제가 있습니다 ❌")
sys.exit(0 if ok else 1)
