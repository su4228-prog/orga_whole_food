"""벡터 검색(RAG) — 이용 안내 문서와 상품 설명을 조각으로 나눠 Supabase(pgvector)에 저장하고,
질문과 의미가 가장 가까운 조각만 골라 상담봇에게 건넵니다.

- 임베딩: OpenAI text-embedding-3-small (숫자 1536개, 아주 저렴)
- 저장 · 검색: Supabase rag_chunks 표 + match_rag_chunks 함수 (sql/002_vector_rag.sql)
- 표가 아직 없거나 검색이 실패하면 available() 이 False 가 되고, 상담봇은 문서 전체를 넣는 예전 방식으로 동작합니다.
"""
import json
import logging
import re
import time
from pathlib import Path

from openai import OpenAI

from config import OPENAI_API_KEY
from db import get_client

log = logging.getLogger("olga.rag")

EMBED_MODEL = "text-embedding-3-small"
BACKEND_DIR = Path(__file__).resolve().parents[1]
POLICY_FILE = BACKEND_DIR / "rag_docs" / "policy.md"
CONTENT_FILE = BACKEND_DIR / "data" / "product_content.json"

_client = None
_state = {"checked_at": 0.0, "ok": False}


def _openai() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY, timeout=20)
    return _client


def embed(texts: list[str]) -> list[list[float]]:
    res = _openai().embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in res.data]


# ───────────────────────── 조각 만들기 ─────────────────────────
def policy_chunks() -> list[dict]:
    """이용 안내를 제목(##, ###) 단위로 자릅니다. 각 조각 앞에 제목을 붙여 조각만 봐도 무슨 내용인지 알게 합니다."""
    chunks, h2, h3, buf = [], "", "", []

    def flush():
        body = "\n".join(buf).strip()
        if len(body) >= 20 and h2:
            title = re.sub(r"^\d+\.\s*", "", h2) + (f" > {h3}" if h3 else "")
            chunks.append({"source": "policy", "title": title, "content": f"[{title}]\n{body}", "metadata": {}})

    for line in POLICY_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            flush(); buf = []; h2, h3 = line[3:].strip(), ""
        elif line.startswith("### "):
            flush(); buf = []; h3 = line[4:].strip()
        elif not line.startswith("# "):
            buf.append(line)
    flush()
    return chunks


def product_chunks(only_id: int | None = None) -> list[dict]:
    """상품 1개 = 조각 1개 (이름 · 가격 · 분류 · 보관 · 소개 · 즐기는 법). only_id 를 주면 그 상품만."""
    db = get_client()
    query = db.table("products").select("*").order("id")
    if only_id is not None:
        query = query.eq("id", only_id)
    products = query.execute().data
    content = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))
    dq = db.table("product_details").select("product_id,detail")
    if only_id is not None:
        dq = dq.eq("product_id", only_id)
    details = {d["product_id"]: d["detail"] for d in dq.execute().data}
    chunks = []
    for p in products:
        c = dict(content.get(p["name"]) or _from_detail(details.get(p["id"], {})))
        # 관리자 화면에서 고친 분류 · 보관 · 설명이 있으면 그것을 우선
        for col, key in (("category", "category"), ("storage", "storage_type"), ("description", "description")):
            if p.get(col):
                c[key] = p[col]
        lines = [f"상품명: {p['name']}", f"브랜드: {p['brand']}"]
        if p.get("price"):
            price = f"판매가: {p['price']:,}원"
            if p.get("discount_rate"):
                price += f" ({p['discount_rate']}% 할인 적용가)"
            lines.append(price)
        if c.get("category"):
            lines.append(f"분류: {c['category']}")
        if c.get("storage_type"):
            lines.append(f"보관: {c['storage_type']}")
        for key in ("description", "intro"):
            if c.get(key):
                lines.append(c[key])
        lines += c.get("tips", [])
        if c.get("storage"):
            lines.append(f"보관 방법: {c['storage']}")
        chunks.append({"source": "product", "title": p["name"], "content": "\n".join(lines),
                       "metadata": {"product_id": p["id"], "image": p.get("image")}})
    return chunks


def _from_detail(detail: dict) -> dict:
    """설명 파일에 없는 상품(직접 만든 원본 상세: 복숭아 병조림)은 상세 페이지 내용에서 설명을 모읍니다."""
    prod = detail.get("product", {})
    storage_type = next((r["value"] for r in prod.get("infoRows", []) if r.get("label") == "보관방법"), "")
    out = {"category": prod.get("category", ""), "storage_type": storage_type,
           "description": prod.get("description", ""), "tips": []}
    for b in detail.get("detailContent", []):
        if b.get("type") == "storyIntro":
            out["intro"] = b.get("desc", "")
        elif b.get("type") == "textSection":
            out["tips"] += b.get("paragraphs", [])
        elif b.get("type") == "storage":
            out["storage"] = b.get("text", "").lstrip("-")
    return out


def rebuild() -> int:
    """조각을 모두 다시 만들어 저장합니다 (scripts/build_rag.py 에서 실행)."""
    chunks = policy_chunks() + product_chunks()
    vectors = embed([c["content"] for c in chunks])
    db = get_client()
    db.table("rag_chunks").delete().neq("id", 0).execute()
    rows = [{**c, "embedding": v} for c, v in zip(chunks, vectors)]
    db.table("rag_chunks").insert(rows).execute()
    _state.update(checked_at=0.0)
    return len(rows)


def upsert_product(pid: int) -> None:
    """상품 1개의 조각만 다시 만듭니다 (관리자 등록 · 수정 직후)."""
    if not available():
        return
    remove_product(pid)
    chunks = product_chunks(only_id=pid)
    if chunks:
        vec = embed([chunks[0]["content"]])[0]
        get_client().table("rag_chunks").insert({**chunks[0], "embedding": vec}).execute()


def remove_product(pid: int) -> None:
    get_client().table("rag_chunks").delete().eq("source", "product") \
        .filter("metadata->>product_id", "eq", str(pid)).execute()


# ───────────────────────── 검색 ─────────────────────────
def available() -> bool:
    """rag_chunks 표에 조각이 있는지 (10분마다 다시 확인)"""
    if not OPENAI_API_KEY:
        return False
    if time.time() - _state["checked_at"] < 600:
        return _state["ok"]
    try:
        rows = get_client().table("rag_chunks").select("id").limit(1).execute().data
        ok = bool(rows)
    except Exception as e:                               # 표가 아직 없음 등
        log.warning("벡터 검색 사용 불가 → 문서 전체 방식으로 대신합니다: %s", e)
        ok = False
    _state.update(checked_at=time.time(), ok=ok)
    return ok


def search(query: str, source: str | None = None, k: int = 5, vector: list[float] | None = None) -> list[dict]:
    """질문과 의미가 가까운 조각 k개 (similarity: 1에 가까울수록 비슷)"""
    vec = vector or embed([query])[0]
    res = get_client().rpc("match_rag_chunks",
                           {"query_embedding": vec, "match_count": k, "filter_source": source}).execute()
    return res.data or []
