"""기존 json/*.json 상품 정보를 Supabase 보관함으로 옮기는 프로그램 (1회용)

실행 (backend 폴더에서):
    .venv\\Scripts\\python scripts\\seed.py --dry-run      # 옮길 내용을 미리 보기만 (아무것도 쓰지 않음)
    .venv\\Scripts\\python scripts\\seed.py                # 실제로 옮기기 (표가 비어 있을 때만 동작)
    .venv\\Scripts\\python scripts\\seed.py --reset        # 표를 비우고 다시 옮기기

규칙
- 가격 "4,200원" → 4200, 할인 "35%" → 35 로 숫자로 바꿔 저장합니다.
- 같은 이름의 상품은 products 에 1줄만 두고, 섹션과는 section_products 로 연결합니다.
- 섹션마다 다른 값(이미지 · 뱃지 · 배송/추가 라벨 · 순서)은 section_products 에 둡니다.
- sub.json 은 같은 이름의 상품(복숭아 병조림)의 product_details 로 저장합니다.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]          # 사이트 폴더
JSON_DIR = ROOT / "json"
load_dotenv(ROOT / "backend" / ".env")

SECTIONS = [  # (key, 파일, 화면 순서)
    ("client", "client_products.json", 1),
    ("discount", "discount_products.json", 2),
    ("gift", "gift_products.json", 3),
    ("md", "md_products.json", 4),
    ("new", "new_products.json", 5),
    ("best", "best_products.json", 6),
]


def to_int(text):
    """'4,200원' → 4200, '35%' → 35, None → None"""
    if text is None:
        return None
    digits = re.sub(r"[^\d]", "", str(text))
    return int(digits) if digits else None


def load_plan():
    """JSON을 읽어 (섹션 목록, 상품 목록, 섹션-상품 연결 목록, 상세) 계획을 만든다."""
    sections, products, links = [], {}, []
    conflicts = []

    for key, filename, order in SECTIONS:
        data = json.loads((JSON_DIR / filename).read_text(encoding="utf-8"))
        meta = {}
        if key == "md":
            meta["banner"] = data.get("banner")
        if key == "best":
            meta["categories"] = data.get("categories", [])
        sections.append({
            "key": key,
            "title": data.get("section_title"),
            "subtitle": data.get("subtitle"),
            "meta": meta,
            "sort_order": order,
        })

        for idx, item in enumerate(data["items"], start=1):
            name = item["name"]
            base = {
                "name": name,
                "brand": item.get("brand") or "올가",
                "image": item.get("image") or item.get("main_image"),
                "price": to_int(item.get("price")),
                "discount_rate": to_int(item.get("discount")),
                "unit_price": item.get("unit_price"),
                "rating": item.get("rating"),
                "review_count": item.get("reviews"),
            }
            if name in products:
                # 같은 상품이 다른 섹션에도 나옴 → 값이 서로 다르면 알려준다 (첫 값을 유지)
                for field in ("price", "discount_rate", "unit_price", "rating", "review_count"):
                    if products[name][field] != base[field]:
                        conflicts.append((name, field, products[name][field], base[field]))
            else:
                products[name] = base

            links.append({
                "section_key": key,
                "name": name,
                "sort_order": item.get("rank", idx),   # 베스트는 순위, 나머지는 나온 순서
                "image": item.get("image") or item.get("main_image"),
                "thumb_image": item.get("thumb"),
                "badge": item.get("badge"),
                "delivery_badge": item.get("delivery_badge"),
                "extra_badge": item.get("extra_badge"),
            })

    detail = json.loads((JSON_DIR / "sub.json").read_text(encoding="utf-8"))
    detail_name = detail["product"]["fullName"]
    return sections, products, links, (detail_name, detail), conflicts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="옮길 내용만 미리 보기 (쓰지 않음)")
    ap.add_argument("--reset", action="store_true", help="기존 표를 비우고 다시 옮기기")
    args = ap.parse_args()

    sections, products, links, (detail_name, detail), conflicts = load_plan()

    print("옮길 계획")
    print(f"  섹션 {len(sections)}개 · 상품 {len(products)}개 (카드 {len(links)}개를 같은 이름끼리 합침) · 상세 1개")
    dup = {}
    for l in links:
        dup.setdefault(l["name"], []).append(l["section_key"])
    for n, secs in dup.items():
        if len(secs) > 1:
            print(f"  · 여러 섹션에 나오는 상품 → 1줄로 합침: {n[:36]} {secs}")
    if conflicts:
        print("  ⚠ 같은 상품인데 섹션마다 값이 다른 항목 (첫 값 사용):")
        for c in conflicts:
            print("    ", c)
    else:
        print("  같은 상품의 가격·할인·단가·평점은 모든 섹션에서 일치합니다.")
    if detail_name not in products:
        sys.exit(f"상세(sub.json)의 상품 '{detail_name}' 이 상품 목록에 없습니다.")
    print(f"  상세 정보 연결 대상: {detail_name}")

    if args.dry_run:
        print("미리 보기만 했습니다. 보관함에는 아무것도 쓰지 않았습니다.")
        return

    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        sys.exit(".env 에 SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 가 필요합니다.")
    from supabase import create_client
    db = create_client(url, key)

    # 이미 데이터가 있으면 멈춘다 (--reset 일 때만 비움)
    existing = {t: db.table(t).select("*", count="exact").limit(1).execute().count
                for t in ("products", "sections", "section_products", "product_details")}
    if any(existing.values()):
        if not args.reset:
            sys.exit(f"보관함에 이미 데이터가 있습니다 {existing}. 다시 옮기려면 --reset 을 붙이세요.")
        print("  --reset: 기존 데이터를 지우고 다시 옮깁니다.")
        db.table("section_products").delete().neq("product_id", 0).execute()
        db.table("product_details").delete().neq("product_id", 0).execute()
        db.table("products").delete().neq("id", 0).execute()
        db.table("sections").delete().neq("key", "").execute()

    # 1) 섹션
    db.table("sections").insert(sections).execute()
    # 2) 상품 (id 는 보관함이 부여)
    res = db.table("products").insert(list(products.values())).execute()
    name_to_id = {row["name"]: row["id"] for row in res.data}
    # 3) 섹션-상품 연결
    rows = []
    for l in links:
        rows.append({
            "section_key": l["section_key"],
            "product_id": name_to_id[l["name"]],
            "sort_order": l["sort_order"],
            "image": l["image"],
            "thumb_image": l["thumb_image"],
            "badge": l["badge"],
            "delivery_badge": l["delivery_badge"],
            "extra_badge": l["extra_badge"],
        })
    db.table("section_products").insert(rows).execute()
    # 4) 상세
    db.table("product_details").insert({"product_id": name_to_id[detail_name], "detail": detail}).execute()

    print("옮기기 완료 ✅")


if __name__ == "__main__":
    main()
