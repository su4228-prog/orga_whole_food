r"""회원에게 관리자 권한 주기 · 빼기 (관리자 권한은 화면에서 줄 수 없고 이 도구나 Supabase 에서만 바꿉니다)

backend 폴더에서:
    .venv\Scripts\python scripts\set_admin.py 아이디          ← 관리자로
    .venv\Scripts\python scripts\set_admin.py 아이디 --remove ← 일반 회원으로
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import get_client  # noqa: E402

if len(sys.argv) < 2:
    sys.exit(__doc__)
login_id = sys.argv[1].strip().lower()
role = "user" if "--remove" in sys.argv else "admin"
rows = get_client().table("users").update({"role": role}).eq("login_id", login_id).execute().data
if not rows:
    sys.exit(f"'{login_id}' 아이디의 회원이 없어요. 먼저 회원가입해 주세요.")
print(f"✅ {rows[0]['name']}({login_id}) → {'관리자' if role == 'admin' else '일반 회원'}")
print("   이미 로그인해 있다면 새로고침하면 바로 반영됩니다.")
