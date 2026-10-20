"""상품 조회 — 보관함에서 꺼내 지금 사이트가 읽는 JSON과 같은 모양으로 돌려줍니다."""
import re
from typing import Any, Optional

from db import get_client

DEFAULT_BRAND_ICON = "./img/icon/green_icon.png"
SEARCH_COLUMNS = "id,name,brand,image,price,discount_rate,unit_price,rating,review_count"


class NotFound(Exception):
    """찾는 섹션/상품이 없을 때"""


# ───────────────────────── 표시용 변환 ─────────────────────────

def won(n: Optional[int]) -> Optional[str]:
    """4200 → '4,200원'"""
    return None if n is None else f"{n:,}원"


def pct(n: Optional[int]) -> Optional[str]:
    """35 → '35%'"""
    return None if n is None else f"{n}%"


def _drop_none(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


# ───────────────────────── 섹션 ─────────────────────────

def list_sections() -> list[dict]:
    rows = get_client().table("sections").select("key,title,subtitle").order("sort_order").execute().data
    return [_drop_none(r) for r in rows]


def _card(section_key: str, row: dict) -> dict:
    p = row["products"]
    item: dict[str, Any] = {
        "id": p["id"],
        "brand": p["brand"],
        "name": p["name"],
        "price": won(p["price"]),
        "discount": pct(p["discount_rate"]),
        "unit_price": p["unit_price"],
        "rating": p["rating"],
        "reviews": p["review_count"],
        "badge": row["badge"],
        "delivery_badge": row["delivery_badge"],
        "extra_badge": row["extra_badge"],
    }
    if section_key == "new":
        item["main_image"] = row["image"]          # 신상품은 큰 이미지 + 썸네일
        item["thumb"] = row["thumb_image"]
    else:
        item["image"] = row["image"]
    if section_key == "best":
        item["rank"] = row["sort_order"]
    return _drop_none(item)


def get_section(key: str) -> dict:
    db = get_client()
    sec = db.table("sections").select("*").eq("key", key).limit(1).execute().data
    if not sec:
        raise NotFound(f"섹션 '{key}' 을(를) 찾을 수 없습니다.")
    sec = sec[0]
    rows = (db.table("section_products")
            .select("sort_order,image,thumb_image,badge,delivery_badge,extra_badge,products(*)")
            .eq("section_key", key).order("sort_order").execute().data)

    out: dict[str, Any] = {"section_title": sec["title"]}
    if sec.get("subtitle"):
        out["subtitle"] = sec["subtitle"]
    meta = sec.get("meta") or {}
    if meta.get("banner"):
        out["banner"] = meta["banner"]
    if meta.get("categories"):
        out["categories"] = meta["categories"]
    out["items"] = [_card(key, r) for r in rows]
    return out


# ───────────────────────── 검색 ─────────────────────────

def search_products(q: str, limit: int = 20) -> list[dict]:
    # 검색 조건 문법을 깨는 글자는 공백으로 바꿔 안전하게 만든다
    q = re.sub(r"[,()*%\\]", " ", q or "").strip()[:50]
    query = get_client().table("products").select(SEARCH_COLUMNS)
    if q:
        query = query.or_(f"name.ilike.*{q}*,brand.ilike.*{q}*")
    rows = query.order("id").limit(limit).execute().data
    return [_drop_none({
        "id": r["id"], "name": r["name"], "brand": r["brand"], "image": r["image"],
        "price": won(r["price"]), "discount": pct(r["discount_rate"]),
        "unit_price": r["unit_price"], "rating": r["rating"], "reviews": r["review_count"],
    }) for r in rows]


# ───────────────────────── 상세 ─────────────────────────

def _original_price(sale: Optional[int], rate: Optional[int]) -> Optional[int]:
    """할인 전 가격을 판매가와 할인율에서 역산. 딱 떨어질 때만 값을 주고, 아니면 None(표시 안 함)."""
    if not sale or not rate or rate >= 100:
        return None
    orig = round(sale / (1 - rate / 100) / 10) * 10          # 10원 단위로 맞춤
    return orig if round(orig * (1 - rate / 100)) == sale else None   # 정확히 맞아떨어질 때만


def _recommend_item(p: dict, link: Optional[dict] = None) -> dict:
    link = link or {}
    return _drop_none({
        "id": p["id"],
        "image": link.get("image") or p["image"],
        "alt": p["name"],
        "badge": link.get("badge"),
        "brand": p["brand"],
        "name": p["name"],
        "discount": p["discount_rate"],
        "price": p["price"],
        "unit": p["unit_price"],
        "rating": p["rating"],
        "reviewCount": p["review_count"],
        "label": link.get("delivery_badge"),
    })


def _related(pid: int, section_keys: list[str], limit: int = 10) -> list[dict]:
    """같은 섹션의 다른 상품을 우선으로, 모자라면 다른 상품으로 채운 연관 상품"""
    db = get_client()
    picked: dict[int, dict] = {}
    if section_keys:
        rows = (db.table("section_products")
                .select("image,badge,delivery_badge,sort_order,products(*)")
                .in_("section_key", section_keys).order("sort_order").execute().data)
        for r in rows:
            p = r["products"]
            if p["id"] != pid and p["id"] not in picked:
                picked[p["id"]] = _recommend_item(p, r)
            if len(picked) >= limit:
                break
    if len(picked) < limit:
        for p in db.table("products").select("*").order("id").limit(40).execute().data:
            if p["id"] != pid and p["id"] not in picked:
                picked[p["id"]] = _recommend_item(p)
            if len(picked) >= limit:
                break
    return list(picked.values())


def _basic_detail(prod: dict, links: list[dict]) -> dict:
    """긴 상세 설명이 없는 상품 — 카드 정보로 기본 상세를 구성"""
    badge = next((l["badge"] for l in links if l.get("badge")), None)
    free = any(l.get("delivery_badge") == "무료배송" for l in links)
    lines = ["무료배송 상품"] if free else ["40,000원 미만 구매 시 3,000원"]
    rc = prod["review_count"] or 0
    return {
        "product": {
            "category": "",
            "brand": {"icon": DEFAULT_BRAND_ICON, "name": prod["brand"]},
            "badge": badge,
            "nameLines": [prod["name"]],
            "fullName": prod["name"],
            "description": "",
            "price": {
                "original": _original_price(prod["price"], prod["discount_rate"]),
                "sale": prod["price"],
                "discountRate": prod["discount_rate"],
                "unit": prod["unit_price"] or "",
            },
            "infoRows": [],
            "delivery": {
                "types": [{"icon": "🚚", "label": "일반배송"}, {"icon": "☾", "label": "새벽배송"}],
                "details": [
                    {"icon": "🚚", "title": "일반배송", "lines": lines},
                    {"icon": "☾", "title": "새벽배송", "lines": lines},
                ],
            },
            "gallery": {
                "mainImage": prod["image"], "mainAlt": prod["name"],
                "thumbnails": [{"image": prod["image"], "alt": prod["name"]}],
            },
            "reviewCount": rc,
        },
        "infoTabs": [
            {"label": "상품정보", "active": True},
            {"label": "구매정보"},
            {"label": "상품후기", "count": rc},
            {"label": "상품문의"},
            {"label": "배송/환불"},
        ],
        "detailContent": [{
            "type": "textSection",
            "heading": "상세 정보 준비 중",
            "paragraphs": ["이 상품의 상세 설명은 준비 중입니다."],
        }],
    }


def get_product(pid: int) -> dict:
    db = get_client()
    prods = db.table("products").select("*").eq("id", pid).limit(1).execute().data
    if not prods:
        raise NotFound(f"상품 {pid} 번을 찾을 수 없습니다.")
    prod = prods[0]
    det = db.table("product_details").select("detail").eq("product_id", pid).limit(1).execute().data
    if det:                                   # 긴 상세 설명이 준비된 상품 — 저장된 내용 그대로
        d = det[0]["detail"]
        ai = d.get("aiRecommend")
        if not ai:   # 자동으로 만든 상세는 연관 상품을 저장하지 않고 그때그때 같은 섹션 상품으로 채움
            links = db.table("section_products").select("section_key").eq("product_id", pid).execute().data
            ai = _related(pid, [l["section_key"] for l in links])
        return {"id": pid, "hasFullDetail": True, "product": d["product"],
                "aiRecommend": ai, "infoTabs": d["infoTabs"],
                "detailContent": d["detailContent"]}

    links = db.table("section_products").select("*").eq("product_id", pid).execute().data
    basic = _basic_detail(prod, links)
    return {"id": pid, "hasFullDetail": False, "product": basic["product"],
            "aiRecommend": _related(pid, [l["section_key"] for l in links]),
            "infoTabs": basic["infoTabs"], "detailContent": basic["detailContent"]}
