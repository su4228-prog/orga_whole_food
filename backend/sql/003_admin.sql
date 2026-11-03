-- ============================================================
-- 관리자 상품 관리 + AI 상품등록 기록 표 만들기
-- 사용법: Supabase 왼쪽 메뉴 'SQL Editor' → New query → 이 내용을 통째로 붙여넣고 Run
-- 여러 번 실행해도 안전합니다 (이미 있으면 건너뜀).
-- ============================================================

-- 1) 상품 표에 관리자 화면용 칸 추가 (검색 · 수정에 사용)
alter table products add column if not exists category    text;              -- 분류 (과일, 국·반찬 …)
alter table products add column if not exists storage     text;              -- 보관 (실온보관 / 냉장보관 / 냉동보관)
alter table products add column if not exists description text;              -- 한 줄 설명
alter table products add column if not exists source      text not null default 'seed';  -- seed(원본) / admin(관리자 등록)
alter table products add column if not exists updated_at  timestamptz;

-- 2) 상품 이미지 경로 기록
create table if not exists product_images (
  id         bigint generated always as identity primary key,
  product_id bigint not null references products(id) on delete cascade,
  url        text   not null,                    -- 이미지 주소 (Supabase Storage 공개 주소 또는 ./img/...)
  is_main    boolean not null default true,
  created_at timestamptz not null default now()
);

-- 3) 관리자 작업 기록 (등록 · 수정 · 삭제)
create table if not exists admin_action_logs (
  id           bigint generated always as identity primary key,
  action       text   not null check (action in ('create', 'update', 'delete')),
  product_id   bigint,                           -- 삭제된 상품도 기록이 남도록 연결(FK)은 걸지 않음
  product_name text,
  detail       jsonb  not null default '{}'::jsonb,   -- 바뀐 내용
  ip           text,
  created_at   timestamptz not null default now()
);

-- 4) AI 분석 기록 (YOLO 결과 + OpenAI Vision 추천)
create table if not exists ai_analysis_logs (
  id          bigint generated always as identity primary key,
  file_name   text,
  yolo        jsonb  not null default '[]'::jsonb,    -- YOLO 가 찾은 물체
  result      jsonb  not null default '{}'::jsonb,    -- AI 가 추천한 상품명 · 가격 · 분류 · 보관
  model       text,
  elapsed_ms  integer,
  product_id  bigint references products(id) on delete set null,   -- 이 분석으로 등록된 상품
  created_at  timestamptz not null default now()
);

create index if not exists products_category_idx      on products (category);
create index if not exists admin_action_logs_time_idx on admin_action_logs (created_at desc);
create index if not exists ai_analysis_logs_time_idx  on ai_analysis_logs (created_at desc);

-- 5) 보안: 새 표는 서버(service_role)만 읽고 씁니다. 브라우저(anon)에서는 접근 불가.
alter table product_images    enable row level security;
alter table admin_action_logs enable row level security;
alter table ai_analysis_logs  enable row level security;
grant all on table product_images, admin_action_logs, ai_analysis_logs to service_role;
grant usage, select on all sequences in schema public to service_role;
