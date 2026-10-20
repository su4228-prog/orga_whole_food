"""상세 설명이 없는 상품에 복숭아 병조림처럼 '상세 설명 블록'을 만들어 보관함에 저장합니다.

문구는 backend/data/product_content.json 에서, 가격·이미지·평점은 보관함(products)에서 가져와 조립합니다.
이미 사람이 만든 상세(복숭아 병조림)는 건드리지 않고, 이 프로그램이 만든 상세(generated)만 다시 만듭니다.

실행 (backend 폴더에서):
    .venv\\Scripts\\python scripts\\build_details.py --dry-run   # 미리 보기만
    .venv\\Scripts\\python scripts\\build_details.py             # 저장
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import get_client  # noqa: E402
from services.product_service import _original_price  # noqa: E402

CONTENT = Path(__file__).resolve().parents[1] / "data" / "product_content.json"
SITE_DIR = Path(__file__).resolve().parents[2]
LOGO = "./img/sub/product_info/0.PNG"
BRAND_MESSAGE = "./img/sub/product_info/08.jpg"
CHECK_ICON = "./img/icon/check_icon.png"
BRAND_ICON = "./img/icon/green_icon.png"


def split_name(name):
    """'상품명 (백도/황도) (450gx2병)' → ['상품명 (백도/황도)', '(450gx2병)'] 처럼 마지막 괄호를 둘째 줄로"""
    m = re.match(r"^(.*\S)\s+(\([^()]*\))$", name)
    return [m.group(1), m.group(2)] if m else [name]


def composition(name):
    """상품명에서 중량·구성을 찾는다: 마지막 괄호 또는 '800g' 같은 표기"""
    m = re.search(r"\(([^()]*\d[^()]*)\)\s*$", name)
    if m:
        return m.group(1)
    m = re.search(r"(\d+(?:\.\d+)?\s?(?:kg|g|ml|입|개입))\s*$", name)
    if m:
        return m.group(1)
    m = re.search(r"(\d+호)\s*$", name)
    return f"{m.group(1)} 세트" if m else "상품 표시 사항 참조"


def build(prod, links, c):
    name = prod["name"]
    images, seen = [], set()
    candidates = [prod.get("image")] + [l.get(k) for l in sorted(links, key=lambda x: x["section_key"])
                                        for k in ("image", "thumb_image")]
    for img in candidates:
        if not img:
            continue
        path = SITE_DIR / img.lstrip("./")
        key = hashlib.md5(path.read_bytes()).hexdigest() if path.exists() else img   # 파일 내용이 같으면 같은 사진
        if key not in seen:
            seen.add(key)
            images.append(img)

    badge = next((l["badge"] for l in links if l.get("badge")), None)
    free = any(l.get("delivery_badge") == "무료배송" for l in links)
    lines = ["무료배송 상품"] if free else ["40,000원 미만 구매 시 3,000원"]
    sale, rate, unit = prod["price"], prod["discount_rate"], prod["unit_price"]
    rc = prod["review_count"] or 0

    price_line = f"· 판매가 : {sale:,}원" + (f" ({rate}% 할인)" if rate else "")
    box_lines = [f"· 구성 : {composition(name)}"]
    if unit:
        box_lines.append(f"· 단위 가격 : {unit.strip('()')}")
    box_lines.append(price_line)

    blocks = [
        {"type": "image", "variant": "logo", "src": LOGO, "alt": "ORGA Whole Foods"},
        {"type": "image", "variant": "product", "src": images[0], "alt": name},
        {"type": "storyIntro", "kicker": c["kicker"], "title": name, "desc": c["intro"],
         "points": [{"icon": CHECK_ICON, "lines": p} for p in c["points"]]},
    ]
    if len(images) > 1:
        blocks.append({"type": "image", "variant": "product", "src": images[1], "alt": name + " 상품 이미지"})
    blocks += [
        {"type": "yellowPanel", "extraClass": "composition-after-image", "heading": "구성을 확인하세요",
         "boxes": [{"title": "① " + name, "lines": box_lines}]},
        {"type": "textSection", "heading": c["tips_heading"], "paragraphs": c["tips"]},
        {"type": "storage", "heading": "보관법", "text": "- " + c["storage"],
         "note": "※ 원산지 · 보관 방법 등 정확한 상품 정보는 받으신 상품의 표시 사항을 확인해 주세요."},
        {"type": "brandMessage", "src": BRAND_MESSAGE, "alt": "ORGA 브랜드 안내"},
    ]

    return {
        "generated": True,  # 이 프로그램이 만든 상세 표시 (다시 만들 때 덮어써도 되는지 판단)
        "product": {
            "category": c["category"],
            "brand": {"icon": BRAND_ICON, "name": prod["brand"]},
            "badge": badge,
            "nameLines": split_name(name),
            "fullName": name,
            "description": c["description"],
            "price": {"original": _original_price(sale, rate), "sale": sale, "discountRate": rate, "unit": unit or ""},
            "infoRows": [
                {"rowClass": "origin-row", "label": "원산지", "value": "상세설명참조"},
                {"rowClass": "storage-row", "label": "보관방법", "value": c["storage_type"]},
            ],
            "delivery": {
                "types": [{"icon": "🚚", "label": "일반배송"}, {"icon": "☾", "label": "새벽배송"}],
                "details": [{"icon": "🚚", "title": "일반배송", "lines": lines},
                            {"icon": "☾", "title": "새벽배송", "lines": lines}],
            },
            "gallery": {"mainImage": images[0], "mainAlt": name,
                        "thumbnails": [{"image": i, "alt": f"{name} 이미지 {n}"} for n, i in enumerate(images, 1)]},
            "reviewCount": rc,
        },
        "infoTabs": [{"label": "상품정보", "active": True}, {"label": "구매정보"},
                     {"label": "상품후기", "count": rc}, {"label": "상품문의"}, {"label": "배송/환불"}],
        "detailContent": blocks,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    content = {k: v for k, v in json.loads(CONTENT.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    db = get_client()
    products = db.table("products").select("*").order("id").execute().data
    links = db.table("section_products").select("*").execute().data
    existing = {d["product_id"]: d["detail"] for d in db.table("product_details").select("*").execute().data}

    todo, skipped, missing = [], [], []
    for p in products:
        old = existing.get(p["id"])
        if old is not None and not old.get("generated"):
            skipped.append(p["name"])              # 사람이 만든 상세는 그대로 둠
            continue
        c = content.get(p["name"])
        if not c:
            missing.append(p["name"])
            continue
        todo.append({"product_id": p["id"],
                     "detail": build(p, [l for l in links if l["product_id"] == p["id"]], c)})

    print(f"만들 상세 {len(todo)}개 · 그대로 둘 상세 {len(skipped)}개 {skipped} · 문구 없는 상품 {len(missing)}개 {missing}")
    if todo:
        sample = todo[0]["detail"]
        print("예시:", sample["product"]["fullName"], "/", sample["product"]["category"],
              "/ 블록", len(sample["detailContent"]), "개 / 썸네일", len(sample["product"]["gallery"]["thumbnails"]), "개")
    if missing:
        sys.exit("문구가 없는 상품이 있어 멈춥니다. product_content.json 을 확인하세요.")
    if args.dry_run:
        print("미리 보기만 했습니다.")
        return
    db.table("product_details").upsert(todo, on_conflict="product_id").execute()
    print("저장 완료 ✅")


if __name__ == "__main__":
    main()
