"""상담봇 벡터 검색(RAG) 보관함 채우기

먼저 Supabase SQL Editor 에서 sql/002_vector_rag.sql 을 한 번 실행한 뒤,
backend 폴더에서:  .venv\\Scripts\\python scripts\\build_rag.py
                     .venv\\Scripts\\python scripts\\build_rag.py --dry-run   ← 조각만 보고 저장은 안 함

이용 안내(policy.md)나 상품 설명(data/product_content.json)을 고쳤다면 다시 실행합니다. (OpenAI 임베딩 요금: 1원 미만)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import rag_service  # noqa: E402

if "--dry-run" in sys.argv:
    chunks = rag_service.policy_chunks() + rag_service.product_chunks()
    for c in chunks:
        print(f"[{c['source']}] {c['title']}  ({len(c['content'])}자)")
    print(f"조각 {len(chunks)}개 (저장하지 않음)")
    sys.exit(0)

n = rag_service.rebuild()
print(f"조각 {n}개 저장 완료 ✅")
hits = rag_service.search("신선식품 반품 기한", k=3)
for h in hits:
    print(f"  검색 확인 · {h['similarity']:.2f}  {h['title']}")
