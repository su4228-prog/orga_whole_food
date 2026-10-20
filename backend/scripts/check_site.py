"""사이트 전체 점검 — 서버를 켠 상태에서 실행합니다. (읽기만 함 · 상담봇 질문은 보내지 않음)

실행 (backend 폴더에서):  .venv\\Scripts\\python scripts\\check_site.py
필요: playwright (pip install playwright) + 크롬
"""
import sys

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
res = []


def check(label, cond, detail=""):
    res.append(bool(cond))
    print(("  ✅ " if cond else "  ❌ ") + label + (f"  {detail}" if detail else ""))


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs, bad = [], []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(f"{m.text} {m.location.get('url', '')}")
          if m.type == "error" and "favicon" not in m.location.get("url", "") else None)
    pg.on("response", lambda r: bad.append((r.status, r.url)) if r.status >= 400 and "favicon" not in r.url else None)

    print("1) 메인 페이지")
    pg.goto(BASE + "/", wait_until="networkidle"); pg.wait_for_timeout(800)
    check("상품 카드 33개", pg.locator("article").count() == 33)
    check("상품 카드 이미지 36곳이 각자 상세로 연결", pg.evaluate("document.querySelectorAll('a.card-link[href^=\"sub.html?id=\"]').length") == 36)
    check("배너 · 카테고리 · 광고 배너는 이동하지 않음",
          pg.evaluate("[...document.querySelectorAll('.slide,.category-item,.ad-card,.md-banner')].filter(a=>a.hasAttribute('href')).length") == 0)
    check("깨진 이미지 0", pg.evaluate("[...document.images].filter(i=>!i.complete||i.naturalWidth===0).length") == 0)
    tb = pg.locator(".chat-toggle").bounding_box()
    check("상담봇 로봇 버튼이 왼쪽 아래", tb and tb["x"] < 100 and tb["y"] > 780, str({k: round(v) for k, v in (tb or {}).items()}))
    pg.evaluate("window.scrollTo(0, 4000)"); pg.wait_for_timeout(300)
    tb2 = pg.locator(".chat-toggle").bounding_box()
    check("스크롤해도 같은 자리 (엘리베이터)", tb2 and round(tb2["x"]) == round(tb["x"]) and round(tb2["y"]) == round(tb["y"]))
    pg.click(".chat-toggle"); pg.wait_for_timeout(400)
    pb = pg.locator(".chat-panel").bounding_box()
    check("상담봇 창이 왼쪽 아래에서 열림", pg.locator(".chat-panel").is_visible() and pb["x"] < 100)
    pg.keyboard.press("Escape")

    print("2) 상품 상세 30개")
    ids = sorted({int(h.split("=")[1]) for h in pg.evaluate("[...document.querySelectorAll('a.card-link')].map(a=>a.getAttribute('href'))")})
    problems = []
    for i in ids:
        pg.goto(f"{BASE}/sub.html?id={i}", wait_until="networkidle"); pg.wait_for_timeout(200)
        ok = pg.evaluate("""()=>!!document.querySelector('.product-name')?.innerText &&
            document.getElementById('productInfoContent').children.length >= 7 &&
            document.querySelectorAll('.ai-card').length === 10 &&
            [...document.images].every(x=>!x.complete||x.naturalWidth>0)""")
        if not ok:
            problems.append(i)
    check(f"상세 {len(ids)}개 모두 정상 (이름 · 상세 블록 · 연관 상품 · 이미지)", len(ids) == 30 and not problems, str(problems))
    a = pg.locator(".chat-toggle").bounding_box(); t = pg.locator("#floatingTop").bounding_box()
    check("상세 페이지: 상담봇(왼쪽)과 맨 위로 버튼(오른쪽)이 겹치지 않음", a["x"] + a["width"] < t["x"])
    check("JS 오류 0", not errs, str(errs)[:200])
    check("HTTP 오류 0", not bad, str(bad)[:200])
    pg.goto(f"{BASE}/sub.html?id=999999", wait_until="networkidle"); pg.wait_for_timeout(300)
    check("없는 상품 번호 → 안내 문구", "찾으시는 상품이 없습니다" in pg.inner_text("body"))

    print("3) 화면 폭별 가로 넘침")
    over = {}
    for w in (1440, 1100, 900, 760, 560, 390):
        q = b.new_page(viewport={"width": w, "height": 900})
        for name, url in (("메인", "/"), ("상세", "/sub.html?id=9")):
            q.goto(BASE + url, wait_until="networkidle"); q.wait_for_timeout(300)
            d = q.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth")
            if d > 0:
                over[f"{name} {w}px"] = d
        q.close()
    check("가로 넘침 없음 (알려진 항목: 상세 390px)", set(over) <= {"상세 390px"}, str(over))

    print("4) 보안")
    for path in ("/backend/.env", "/backend/app.py", "/.git/config", "/backend/rag_docs/policy.md"):
        r = pg.request.get(BASE + path)
        check(f"{path} 는 열리지 않음", r.status == 404, str(r.status))
    b.close()

print("결과:", "모두 통과 ✅" if all(res) else f"실패 {res.count(False)}건 ❌")
sys.exit(0 if all(res) else 1)
