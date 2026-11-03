"""원본 상품 30개의 분류 · 보관 · 설명 칸 채우기 (관리자 화면의 검색 · 수정용)

먼저 Supabase SQL Editor 에서 sql/003_admin.sql 을 한 번 실행한 뒤,
backend 폴더에서:  .venv\\Scripts\\python scripts\\backfill_products.py

이미 값이 있는 칸(관리자가 고친 값)은 건드리지 않습니다.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import get_client  # noqa: E402
from services.rag_service import CONTENT_FILE, _from_detail  # noqa: E402

db = get_client()
content = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))
details = {d["product_id"]: d["detail"] for d in db.table("product_details").select("product_id,detail").execute().data}
images = {r["product_id"] for r in db.table("product_images").select("product_id").execute().data}

filled = 0
for p in db.table("products").select("*").order("id").execute().data:
    c = content.get(p["name"]) or _from_detail(details.get(p["id"], {}))
    want = {"category": c.get("category"), "storage": c.get("storage_type"), "description": c.get("description")}
    update = {k: v for k, v in want.items() if v and not p.get(k)}
    if update:
        db.table("products").update(update).eq("id", p["id"]).execute()
        filled += 1
    if p["id"] not in images and p.get("image"):
        db.table("product_images").insert({"product_id": p["id"], "url": p["image"], "is_main": True}).execute()
    print(f"  #{p['id']:>2} {p['name'][:24]:<24} {update or '그대로'}")
print(f"완료 ✅  칸을 채운 상품 {filled}개")
