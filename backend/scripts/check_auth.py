r"""회원 · 관리자 점검 — 서버를 켠 상태에서 실행합니다.

시험용 계정을 만들어 가입 → 로그인 유지 → 권한 → 로그아웃까지 브라우저로 확인하고, 끝나면 계정을 지웁니다.
실행 (backend 폴더에서):  .venv\\Scripts\\python scripts\\check_auth.py [서버주소]
필요: playwright (pip install playwright) + 크롬
"""
import secrets
import sys
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import get_client  # noqa: E402

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
WAIT = 40000                                         # 무료 서버는 응답이 느릴 수 있어 넉넉히
uid = "qa" + secrets.token_hex(3)
pw = "Qa" + secrets.token_hex(5) + "9"
results = []


def check(label, cond, detail=""):
    results.append(bool(cond))
    print(("  ✅ " if cond else "  ❌ ") + label + (f"  {detail}" if detail else ""))


def set_role(role):
    get_client().table("users").update({"role": role}).eq("login_id", uid).execute()


try:
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        print("1) 가입 · 로그인 유지")
        pg.goto(BASE + "/signup.html", wait_until="networkidle")
        pg.fill("#suId", "admin"); pg.click("#checkIdBtn")
        pg.wait_for_function("document.querySelector('#idHint').textContent.includes('이미')", timeout=WAIT)
        check("이미 있는 아이디 → 사용 중 안내", True)
        pg.fill("#suId", uid); pg.click("#checkIdBtn")
        pg.wait_for_function("document.querySelector('#idHint').textContent.includes('사용할 수 있는')", timeout=WAIT)
        pg.fill("#suPw", pw); pg.fill("#suPw2", pw); pg.fill("#suName", "시험")
        pg.check("#agreeAll"); pg.click("#signupBtn")
        pg.wait_for_url(BASE + "/index.html", timeout=WAIT)
        pg.wait_for_function("document.querySelector('.member-links').innerText.includes('로그아웃')", timeout=WAIT)
        check("가입 → 자동 로그인 → 헤더 '시험님'", "시험" in pg.inner_text(".member-links"))

        cookie = next((c for c in ctx.cookies() if c["name"] == "orga_session"), None)
        check("출입증은 HttpOnly 쿠키 (스크립트로 읽을 수 없음)", cookie and cookie["httpOnly"])
        check("브라우저 저장소에 출입증 없음",
              pg.evaluate("Object.keys(localStorage).every(k => !/token/.test(k)) && !document.cookie.includes('orga_session')"))
        pg.reload(wait_until="networkidle")
        pg.wait_for_function("document.querySelector('.member-links').innerText.includes('로그아웃')", timeout=WAIT)
        check("새로고침해도 로그인 유지", True)

        print("2) 권한")
        pg.goto(BASE + "/admin.html", wait_until="networkidle")
        pg.wait_for_selector("#loginCard:not([hidden])", timeout=WAIT)
        check("일반 회원은 관리자 페이지 차단", "권한이 없는" in pg.inner_text("#loginCard"))
        set_role("admin")
        pg.goto(BASE + "/admin.html", wait_until="networkidle")
        pg.wait_for_selector("#productRows tr", timeout=WAIT)
        check("관리자로 바꾸면 새로고침만으로 입장 · 목록 표시", pg.locator("#productRows tr").count() == 5)

        token = cookie["value"]
        api = httpx.Client(base_url=BASE, timeout=60)
        r = api.delete("/api/admin/products/999999", cookies={"orga_session": token})
        check("쿠키만 있고 사이트 머리말이 없는 변경 요청 차단 (위조 요청 방지)", r.status_code == 403, str(r.status_code))
        r = api.get("/api/admin/products", headers={"Authorization": "Bearer 9999999999.fake"})
        check("가짜 출입증 거절", r.status_code == 401, str(r.status_code))

        print("3) 로그아웃 · 틀린 비밀번호")
        pg.goto(BASE + "/", wait_until="networkidle")
        pg.wait_for_function("document.querySelector('.member-links').innerText.includes('관리자')", timeout=WAIT)
        check("관리자에게만 헤더 '관리자' 메뉴", True)
        pg.click(".member-links >> text=로그아웃")
        pg.wait_for_function("document.querySelector('.member-links').innerText.includes('로그인')", timeout=WAIT)
        check("로그아웃 → 헤더 '로그인' · 쿠키 삭제",
              not any(c["name"] == "orga_session" for c in ctx.cookies()))
        pg.goto(BASE + "/login.html", wait_until="networkidle")
        pg.fill("#loginId", uid); pg.fill("#loginPw", "wrong-pass1"); pg.click("#loginBtn")
        pg.wait_for_function("document.querySelector('#loginMsg').textContent.length > 0", timeout=WAIT)
        check("틀린 비밀번호 → 안내", "맞지 않아요" in pg.inner_text("#loginMsg"))
        check("JS 오류 0", not errors, str(errors)[:200])
        b.close()
finally:
    get_client().table("users").delete().eq("login_id", uid).execute()
    print(f"시험 계정 {uid} 삭제")

print("결과:", "모두 통과 ✅" if all(results) else f"실패 {results.count(False)}건 ❌")
sys.exit(0 if all(results) else 1)
