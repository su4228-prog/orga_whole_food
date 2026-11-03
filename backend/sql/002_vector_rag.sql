-- ============================================================
-- 상담봇 벡터 검색(RAG) 보관함 만들기
-- 사용법: Supabase 왼쪽 메뉴 'SQL Editor' → New query → 이 내용을 통째로 붙여넣고 Run
-- 여러 번 실행해도 안전합니다 (이미 있으면 건너뜀).
--
-- 이용 안내 문서와 상품 설명을 작은 조각으로 나눠, 각 조각의 "의미 좌표"(임베딩, 숫자 1536개)를 저장합니다.
-- 질문이 들어오면 질문의 좌표와 가장 가까운 조각만 골라 상담봇에게 건넵니다.
-- ============================================================

-- 1) 벡터 기능 켜기 (Supabase 무료 요금제에서도 사용 가능)
create extension if not exists vector with schema extensions;

-- 2) 조각 표
create table if not exists rag_chunks (
  id         bigint generated always as identity primary key,
  source     text  not null,                     -- 'policy'(이용 안내) 또는 'product'(상품)
  title      text  not null,                     -- 화면에 보여줄 출처 이름 (예: 반품 · 교환 · 환불)
  content    text  not null,                     -- 조각 본문
  metadata   jsonb not null default '{}'::jsonb, -- 상품 번호 등
  embedding  extensions.vector(1536) not null,   -- OpenAI text-embedding-3-small
  created_at timestamptz not null default now()
);

create index if not exists rag_chunks_embedding_idx
  on rag_chunks using hnsw (embedding extensions.vector_cosine_ops);

-- 3) 비슷한 조각 찾기 함수 (코사인 유사도가 높은 순)
create or replace function match_rag_chunks(
  query_embedding extensions.vector(1536),
  match_count     int  default 5,
  filter_source   text default null
)
returns table (id bigint, source text, title text, content text, metadata jsonb, similarity float)
language sql stable
set search_path = public, extensions
as $$
  select c.id, c.source, c.title, c.content, c.metadata,
         1 - (c.embedding <=> query_embedding) as similarity
  from rag_chunks c
  where filter_source is null or c.source = filter_source
  order by c.embedding <=> query_embedding
  limit match_count;
$$;

-- 4) 보안: 이 표는 서버(service_role)만 읽고 씁니다. 브라우저(anon)에서는 접근 불가.
alter table rag_chunks enable row level security;
grant all on table rag_chunks to service_role;
grant execute on function match_rag_chunks(extensions.vector, int, text) to service_role;
revoke execute on function match_rag_chunks(extensions.vector, int, text) from anon, authenticated, public;
