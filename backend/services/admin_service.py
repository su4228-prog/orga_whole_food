"""관리자 상품 관리 + AI 상품등록 자동화

AI 상품등록 흐름
  사진 업로드 → YOLO(물체 위치) → OpenAI Vision(상품명 · 가격 · 분류 · 보관 추천) → ai_analysis_logs 기록
  → 관리자가 확인 · 수정 → 등록: products 저장 · 사진은 Supabase Storage · product_images 경로 기록
  → admin_action_logs 작업 기록 → 상담봇 벡터 검색 보관함(rag_chunks)에 이 상품 반영
"""
import base64
import io
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL
from db import get_client
from services import chat_service, rag_service, vision_service
from services.product_service import NotFound, pct, won

log = logging.getLogger("olga.admin")

PAGE_SIZE = 5
BUCKET = "product-images"
CATEGORIES = ["과일", "채소", "쌀·견과", "정육·달걀", "수산", "국·반찬", "간편식", "간식·음료",
              "양념·오일", "건강식품", "견과·가공식품", "생활·뷰티", "기타"]
STORAGES = ["실온보관", "냉장보관", "냉동보관"]
EDITABLE = ("name", "price", "discount_rate", "category", "storage", "description")


class AdminError(ValueError):
    """관리자 요청을 처리할 수 없을 때 — 메시지는 사용자에게 그대로 보여줍니다."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row(p: dict, shown: set[int]) -> dict:
    return {
        "id": p["id"], "name": p["name"], "brand": p["brand"], "image": p.get("image"),
        "price": p.get("price"), "price_text": won(p.get("price")),
        "discount_rate": p.get("discount_rate"), "discount_text": pct(p.get("discount_rate")),
        "category": p.get("category"), "storage": p.get("storage"), "description": p.get("description"),
        "source": p.get("source", "seed"), "on_main": p["id"] in shown,
        "created_at": p.get("created_at"), "updated_at": p.get("updated_at"),
    }


def _shown_ids() -> set[int]:
    """메인 화면 섹션에 진열된 상품 번호"""
    rows = get_client().table("section_products").select("product_id").execute().data
    return {r["product_id"] for r in rows}


def _log(action: str, pid: int | None, name: str | None, detail: dict, ip: str, actor: str | None) -> None:
    try:
        get_client().table("admin_action_logs").insert(
            {"action": action, "product_id": pid, "product_name": name, "detail": detail, "ip": ip, "actor": actor}).execute()
    except Exception:
        log.exception("관리자 작업 기록 실패")


def _after_change(pid: int | None = None, removed: bool = False) -> None:
    """상품이 바뀌면 상담봇이 바로 알도록: 상품 목록 캐시 비우기 + 벡터 보관함 갱신"""
    chat_service.refresh()
    try:
        if pid is not None:
            rag_service.remove_product(pid) if removed else rag_service.upsert_product(pid)
    except Exception:
        log.exception("벡터 보관함 갱신 실패 (scripts/build_rag.py 로 다시 만들 수 있음)")


# ───────────────────────── 목록 · 검색 · 페이지 ─────────────────────────
def list_products(q: str = "", page: int = 1, size: int = PAGE_SIZE) -> dict:
    q = re.sub(r"[,()*%\\]", " ", q or "").strip()[:50]
    query = get_client().table("products").select("*", count="exact")
    if q:
        query = query.or_(f"name.ilike.*{q}*,category.ilike.*{q}*")
    start = (page - 1) * size
    res = query.order("id", desc=True).range(start, start + size - 1).execute()
    total = res.count or 0
    shown = _shown_ids()
    return {"items": [_row(p, shown) for p in res.data], "total": total, "page": page,
            "pages": max(1, -(-total // size)), "size": size, "q": q}


def _get(pid: int) -> dict:
    rows = get_client().table("products").select("*").eq("id", pid).limit(1).execute().data
    if not rows:
        raise NotFound(f"상품 {pid} 번을 찾을 수 없습니다.")
    return rows[0]


def _clean(data: dict) -> dict:
    out = {}
    for k in EDITABLE:
        if k not in data or data[k] is None:
            continue
        v = data[k]
        if k == "name":
            v = str(v).strip()
            if not 2 <= len(v) <= 100:
                raise AdminError("상품명은 2~100자로 입력해 주세요.")
        elif k == "price":
            v = int(v)
            if not 100 <= v <= 10_000_000:
                raise AdminError("판매가는 100원 ~ 1,000만 원 사이로 입력해 주세요.")
        elif k == "discount_rate":
            v = int(v) or None
            if v is not None and not 1 <= v <= 90:
                raise AdminError("할인율은 1~90% 사이로 입력해 주세요.")
        elif k == "category":
            if v not in CATEGORIES:
                raise AdminError("분류를 목록에서 골라 주세요.")
        elif k == "storage":
            v = str(v).strip()[:30]
        elif k == "description":
            v = str(v).strip()[:200] or None
        out[k] = v
    return out


# ───────────────────────── 사진 저장 (Supabase Storage) ─────────────────────────
def _ensure_bucket() -> None:
    storage = get_client().storage
    try:
        storage.get_bucket(BUCKET)
    except Exception:
        storage.create_bucket(BUCKET, options={"public": True, "file_size_limit": 2_000_000,
                                               "allowed_mime_types": ["image/jpeg", "image/png", "image/webp"]})


def _upload(data_url: str) -> str:
    """사진을 다시 JPEG 로 저장해(사진 속 숨은 정보 제거) 공개 주소를 돌려줍니다."""
    img = vision_service.decode(data_url)
    img.thumbnail((1000, 1000))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=86)
    path = f"admin/{datetime.now():%Y%m}/{uuid.uuid4().hex}.jpg"
    _ensure_bucket()
    bucket = get_client().storage.from_(BUCKET)
    bucket.upload(path, buf.getvalue(), {"content-type": "image/jpeg"})
    return bucket.get_public_url(path).rstrip("?")


# ───────────────────────── 등록 · 수정 · 삭제 ─────────────────────────
def create_product(data: dict, image: str | None, analysis_id: int | None, ip: str, actor: str | None = None) -> dict:
    fields = _clean(data)
    for need in ("name", "price", "category"):
        if need not in fields:
            raise AdminError("상품명 · 판매가 · 분류는 꼭 입력해 주세요.")
    if not image:
        raise AdminError("상품 사진을 올려 주세요.")
    url = _upload(image)
    db = get_client()
    row = db.table("products").insert({**fields, "brand": "올가", "image": url, "source": "admin"}).execute().data[0]
    db.table("product_images").insert({"product_id": row["id"], "url": url, "is_main": True}).execute()
    if analysis_id:
        db.table("ai_analysis_logs").update({"product_id": row["id"]}).eq("id", analysis_id).execute()
    _log("create", row["id"], row["name"], {**fields, "image": url, "analysis_id": analysis_id}, ip, actor)
    _after_change(row["id"])
    return _row(row, set())


def update_product(pid: int, data: dict, ip: str, actor: str | None = None) -> dict:
    before = _get(pid)
    fields = _clean(data)
    if not fields:
        raise AdminError("바꿀 내용이 없어요.")
    changed = {k: {"before": before.get(k), "after": v} for k, v in fields.items() if before.get(k) != v}
    if not changed:
        return _row(before, _shown_ids())
    row = get_client().table("products").update({**fields, "updated_at": _now()}).eq("id", pid).execute().data[0]
    _log("update", pid, row["name"], changed, ip, actor)
    _after_change(pid)
    return _row(row, _shown_ids())


def delete_product(pid: int, ip: str, actor: str | None = None) -> dict:
    p = _get(pid)
    if pid in _shown_ids():
        raise AdminError("메인 화면에 진열된 원본 상품은 삭제할 수 없어요. 관리자가 등록한 상품만 삭제할 수 있어요.")
    db = get_client()
    paths = [r["url"].split(f"/{BUCKET}/", 1)[1] for r in
             db.table("product_images").select("url").eq("product_id", pid).execute().data if f"/{BUCKET}/" in r["url"]]
    db.table("products").delete().eq("id", pid).execute()      # product_images 는 함께 지워짐
    if paths:                                                  # 저장소의 사진 파일도 정리
        try:
            db.storage.from_(BUCKET).remove(paths)
        except Exception:
            log.exception("사진 파일 삭제 실패")
    _log("delete", pid, p["name"], {"price": p.get("price"), "category": p.get("category"), "image": p.get("image")}, ip, actor)
    _after_change(pid, removed=True)
    return {"deleted": pid}


def logs(limit: int = 10) -> dict:
    db = get_client()
    actions = db.table("admin_action_logs").select("*").order("created_at", desc=True).limit(limit).execute().data
    analyses = db.table("ai_analysis_logs").select("id,file_name,result,yolo,model,elapsed_ms,product_id,created_at") \
        .order("created_at", desc=True).limit(limit).execute().data
    return {"actions": actions, "analyses": analyses}


# ───────────────────────── AI 분석 (YOLO + OpenAI Vision) ─────────────────────────
VISION_PROMPT = """당신은 유기농 식품 쇼핑몰 '올가'의 상품 등록 도우미입니다.
사진을 보고 쇼핑몰에 올릴 상품 정보를 추천하세요. 반드시 JSON 하나만 답합니다.

{{"name": "상품명 (용량·수량이 보이면 괄호로, 예: 유기농 레몬 (1kg))",
  "price": 판매가 숫자(원, 정수),
  "category": "{categories} 중 하나",
  "storage": "실온보관 / 냉장보관 / 냉동보관 중 하나",
  "description": "40자 이내 한 줄 설명 (효능·건강 효과는 쓰지 않음)",
  "note": "사진에서 확인한 근거 한 줄"}}

참고
- YOLO 물체 인식 결과: {yolo}
- 이 쇼핑몰의 비슷한 상품 가격: {prices}
- 포장 글씨가 보이면 그대로 활용하고, 모르는 정보는 지어내지 말고 일반적인 이름으로 씁니다."""


def _price_examples() -> str:
    rows = get_client().table("products").select("name,price").order("id").limit(30).execute().data
    return ", ".join(f"{r['name']} {r['price']:,}원" for r in rows[:12] if r.get("price"))


def analyze(image: str, file_name: str | None) -> dict:
    if not OPENAI_API_KEY:
        raise AdminError("OpenAI 키가 없어 AI 분석을 할 수 없어요.")
    started = time.time()
    img = vision_service.decode(image)
    detections = vision_service.detect(img) if vision_service.enabled() else []
    yolo_text = ", ".join(f"{d['label_ko']}({round(d['score'] * 100)}%)" for d in detections) or "찾은 물체 없음"

    small = img.copy()
    small.thumbnail((768, 768))
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=85)
    data_url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    prompt = VISION_PROMPT.format(categories=", ".join(CATEGORIES), yolo=yolo_text, prices=_price_examples())
    res = OpenAI(api_key=OPENAI_API_KEY, timeout=40).chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_url, "detail": "low"}},
        ]}],
        response_format={"type": "json_object"},
        max_completion_tokens=300,
    )
    try:
        raw = json.loads(res.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        raw = {}

    result = {
        "name": str(raw.get("name") or "").strip()[:100],
        "price": None, "category": raw.get("category") if raw.get("category") in CATEGORIES else "기타",
        "storage": raw.get("storage") if raw.get("storage") in STORAGES else "실온보관",
        "description": str(raw.get("description") or "").strip()[:200],
        "note": str(raw.get("note") or "").strip()[:200],
    }
    try:
        price = int(round(float(raw.get("price")) / 10) * 10)       # 10원 단위로
        result["price"] = price if 100 <= price <= 10_000_000 else None
    except (TypeError, ValueError):
        pass

    elapsed = int((time.time() - started) * 1000)
    log_id = None
    try:
        log_id = get_client().table("ai_analysis_logs").insert({
            "file_name": (file_name or "")[:120], "yolo": detections, "result": result,
            "model": OPENAI_MODEL, "elapsed_ms": elapsed}).execute().data[0]["id"]
    except Exception:
        log.exception("AI 분석 기록 실패")
    return {"analysis_id": log_id, "result": result, "detections": detections, "elapsed_ms": elapsed,
            "categories": CATEGORIES, "storages": STORAGES}
