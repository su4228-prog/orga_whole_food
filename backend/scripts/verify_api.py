"""켜져 있는 서버(기본 127.0.0.1:8000)의 응답이 지금 사이트의 JSON과 같은지 비교합니다. (읽기만 함)

실행:  .venv\\Scripts\\python scripts\\verify_api.py [서버주소]
"""
import json
import sys
from pathlib import Path

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
JSON_DIR = Path(__file__).resolve().parents[2] / "json"
SECTIONS = ["client", "discount", "gift", "md", "new", "best"]

ok = True
def check(label, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(("  ✅ " if cond else "  ❌ ") + label + (f"  {detail}" if detail else ""))

def norm(items):
    """id 는 번호 체계가 달라졌으므로 비교에서 제외, null 과 빠진 값은 같게 본다"""
    return [{k: v for k, v in it.items() if k != "id" and v is not None} for it in items]

c = httpx.Client(base_url=BASE, timeout=30)

print("1) 서버 상태")
r = c.get("/health"); check("/health", r.status_code == 200 and r.json() == {"status": "ok"})
r = c.get("/api/sections"); check("/api/sections 6개", r.status_code == 200 and [s["key"] for s in r.json()] == SECTIONS, str([s["key"] for s in r.json()]))

print("2) 섹션별 응답이 기존 JSON과 같은지 (id 제외)")
for key in SECTIONS:
    src = json.loads((JSON_DIR / f"{key}_products.json").read_text(encoding="utf-8"))
    r = c.get(f"/api/sections/{key}")
    got = r.json()
    same_items = norm(got["items"]) == norm(src["items"])
    same_meta = all(got.get(k) == src.get(k) for k in src if k != "items")
    ids = [i["id"] for i in got["items"]]
    check(f"{key:9} {len(got['items'])}개", r.status_code == 200 and same_items and same_meta and len(set(ids)) == len(ids))

print("3) 상품 번호 · 합쳐진 상품")
secs = {k: c.get(f"/api/sections/{k}").json()["items"] for k in SECTIONS}
def pid_of(section, name_part): return next(i["id"] for i in secs[section] if name_part in i["name"])
for a, b, part in [("client", "best", "파래 김자반"), ("client", "best", "새우만두"), ("discount", "gift", "굴비세트")]:
    check(f"{part}: {a}·{b} 같은 번호", pid_of(a, part) == pid_of(b, part), str(pid_of(a, part)))
all_ids = {i["id"] for items in secs.values() for i in items}
check("서로 다른 상품 30개", len(all_ids) == 30, str(len(all_ids)))

print("4) 상세 — 긴 설명이 있는 상품(복숭아 병조림)은 sub.json 과 동일")
peach = pid_of("discount", "복숭아 병조림")
r = c.get(f"/api/products/{peach}"); d = r.json()
src = json.loads((JSON_DIR / "sub.json").read_text(encoding="utf-8"))
check("hasFullDetail = true", d.get("hasFullDetail") is True)
check("sub.json 내용과 동일", all(d[k] == src[k] for k in ("product", "aiRecommend", "infoTabs", "detailContent")))

print("5) 상세 — 나머지 상품도 자기 정보로 만든 상세 설명이 있음")
other = pid_of("best", "맥반석구이 오징어")
d = c.get(f"/api/products/{other}").json()
p = d["product"]
check("hasFullDetail = true", d["hasFullDetail"] is True)
check("이름 · 가격 · 이미지가 자기 상품", p["fullName"].startswith("맥반석구이 오징어") and p["price"]["sale"] == 6900 and "best_product/02" in p["gallery"]["mainImage"])
check("할인 전 가격이 딱 떨어지지 않으면 표시하지 않음 (30% · 6,900원)", p["price"]["discountRate"] == 30 and p["price"]["original"] is None, f"original={p['price']['original']}")
check("연관 상품 10개 · 자기 자신 제외", len(d["aiRecommend"]) == 10 and all(x["name"] != p["fullName"] for x in d["aiRecommend"]))
check("상세 블록 7개 이상 (소개 · 구성 · 보관법 등)", len(d["detailContent"]) >= 7 and any(x["type"] == "storyIntro" for x in d["detailContent"]))
need = ["category", "brand", "nameLines", "fullName", "description", "price", "infoRows", "delivery", "gallery", "reviewCount"]
check("화면이 쓰는 항목이 모두 있음", all(k in p for k in need))
free = c.get(f"/api/products/{pid_of('best', '한우 불고기')}").json()
check("무료배송 상품은 배송 문구가 다름", free["product"]["delivery"]["details"][0]["lines"] == ["무료배송 상품"])
orig = c.get(f"/api/products/{pid_of('client', '참송이버섯')}").json()["product"]["price"]
check("참송이버섯 35% 130,000원 → 정가 200,000 역산", orig["original"] == 200000, str(orig))

print("6) 검색")
r = c.get("/api/products", params={"q": "김자반"}); res = r.json()
check("'김자반' → 1건", r.status_code == 200 and len(res) == 1 and "김자반" in res[0]["name"])
r = c.get("/api/products", params={"q": "복숭아"}); check("'복숭아' → 1건 이상", r.status_code == 200 and len(r.json()) >= 1, str(len(r.json())))
r = c.get("/api/products", params={"q": ""}); check("빈 검색어 → 기본 20건", len(r.json()) == 20)
r = c.get("/api/products", params={"q": "", "limit": 50}); check("limit=50 → 30건 전체", len(r.json()) == 30)
r = c.get("/api/products", params={"q": "a,b)(*%"}); check("특수문자 검색어도 오류 없이 처리", r.status_code == 200)
r = c.get("/api/products", params={"q": "없는상품없는상품"}); check("결과 없음 → 빈 목록", r.status_code == 200 and r.json() == [])

print("7) 오류 처리")
r = c.get("/api/sections/없는섹션"); check("없는 섹션 → 404", r.status_code == 404, r.json().get("detail", ""))
r = c.get("/api/products/999999"); check("없는 상품 → 404", r.status_code == 404, r.json().get("detail", ""))
r = c.get("/api/products/abc"); check("번호가 숫자가 아니면 → 422", r.status_code == 422)
r = c.post("/api/sections/client"); check("조회 외 요청(POST) 거부", r.status_code in (404, 405))

print("결과:", "모두 통과 ✅" if ok else "실패한 항목이 있습니다 ❌")
sys.exit(0 if ok else 1)
