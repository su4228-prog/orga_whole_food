r"""상품 사진 특징 만들기 — 사진으로 같은 상품 찾기에 씁니다.

먼저 Supabase SQL Editor 에서 sql/005_rate_limit_and_photo.sql 을 한 번 실행한 뒤,
backend 폴더에서:  .venv\Scripts\python scripts\build_photo_vectors.py

상품 사진을 바꾸면 다시 실행합니다. (관리자 화면에서 등록한 상품은 자동으로 만들어집니다)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import get_client  # noqa: E402
from services import vision_service  # noqa: E402

products = get_client().table("products").select("id,name,image").order("id").execute().data
done = 0
for p in products:
    if not p.get("image"):
        continue
    vision_service.save_product_vector(p["id"], p["image"])
    done += 1
    print(f"  #{p['id']:>2} {p['name'][:30]}")
print(f"상품 사진 특징 {done}개 저장 완료 ✅")
