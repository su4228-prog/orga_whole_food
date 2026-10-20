"""옮긴 데이터가 원본 JSON과 같은지 비교 확인 (읽기만 합니다, 아무것도 쓰지 않음)"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parent))
from seed import SECTIONS, JSON_DIR, to_int  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "backend" / ".env")
db = create_client(os.environ["SUPABASE_URL"].strip(), os.environ["SUPABASE_SERVICE_ROLE_KEY"].strip())

ok = True
def check(label, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(("  ✅ " if cond else "  ❌ ") + label + (f"  {detail}" if detail else ""))

products = db.table("products").select("*").execute().data
secs = db.table("sections").select("*").order("sort_order").execute().data
links = db.table("section_products").select("*").execute().data
details = db.table("product_details").select("*").execute().data
by_id = {p["id"]: p for p in products}

print("1) 개수")
check("상품 30줄", len(products) == 30, f"(실제 {len(products)})")
check("섹션 6줄", len(secs) == 6, f"(실제 {len(secs)})")
check("섹션별 상품 연결 33줄", len(links) == 33, f"(실제 {len(links)})")
check("상세정보 30줄 (복숭아 1 + 자동 생성 29)", len(details) == 30 and sum(1 for d in details if d["detail"].get("generated")) == 29, f"(실제 {len(details)})")
check("상품 이름 중복 없음", len({p['name'] for p in products}) == len(products))

print("2) 섹션별로 원본 JSON과 같은지 (이름 · 순서 · 가격 · 할인 · 이미지)")
for key, filename, _ in SECTIONS:
    src = json.loads((JSON_DIR / filename).read_text(encoding="utf-8"))["items"]
    rows = sorted([l for l in links if l["section_key"] == key], key=lambda r: r["sort_order"])
    same = len(rows) == len(src)
    for s_item, row in zip(src, rows):
        p = by_id[row["product_id"]]
        same &= (p["name"] == s_item["name"]
                 and p["price"] == to_int(s_item.get("price"))
                 and p["discount_rate"] == to_int(s_item.get("discount"))
                 and row["image"] == (s_item.get("image") or s_item.get("main_image"))
                 and row["badge"] == s_item.get("badge")
                 and row["delivery_badge"] == s_item.get("delivery_badge")
                 and row["extra_badge"] == s_item.get("extra_badge"))
    check(f"{key:9} {len(rows)}개", same)

print("3) 합쳐진 상품이 여러 섹션에 연결되는지")
for n in ("ORGA 바삭하고 고소한 파래 김자반 (50g)", "얇은피 새우만두 (480g)", "[산지직송]법성포 굴비세트 9호 (950g)"):
    pid = next(p["id"] for p in products if p["name"] == n)
    where = sorted(l["section_key"] for l in links if l["product_id"] == pid)
    check(f"{n[:22]}…", len(where) == 2, str(where))

print("4) 상세정보")
d = next(x for x in details if not x["detail"].get("generated"))
check("복숭아 병조림에 연결", by_id[d["product_id"]]["name"].startswith("복숭아 병조림"))
src = json.loads((JSON_DIR / "sub.json").read_text(encoding="utf-8"))
check("sub.json 내용과 동일", d["detail"] == src)
check("연관상품 10 · 탭 5 · 블록 14", (len(d["detail"]["aiRecommend"]), len(d["detail"]["infoTabs"]), len(d["detail"]["detailContent"])) == (10, 5, 14))

print("5) 섹션 전용 정보 · 숫자 변환")
meta = {s["key"]: s for s in secs}
check("MD 배너 보존", meta["md"]["meta"].get("banner") == "./img/md_prodcut/01.jpg")
check("베스트 카테고리 탭 8개", len(meta["best"]["meta"].get("categories", [])) == 8)
check("가격이 모두 숫자", all(isinstance(p["price"], int) for p in products))
check("신상품(new) 썸네일 3개", sum(1 for l in links if l["section_key"] == "new" and l["thumb_image"]) == 3)

print("결과:", "모두 일치 ✅" if ok else "다른 부분이 있습니다 ❌")
sys.exit(0 if ok else 1)
