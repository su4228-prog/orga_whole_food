-- ============================================================
-- 올가 푸드 상품 보관함 만들기 (표 4장)
-- 사용법: Supabase 왼쪽 메뉴 'SQL Editor' → New query → 이 내용을 통째로 붙여넣고 Run
-- 여러 번 실행해도 안전합니다 (이미 있으면 건너뜀).
-- ============================================================


-- 1) 상품 표 : 상품 1개 = 1줄 (같은 상품은 섹션이 달라도 1줄만 둡니다)
create table if not exists products (
  id             bigint generated always as identity primary key,
  name           text    not null,               -- 상품명
  brand          text    not null default '올가',
  image          text,                           -- 기본 이미지 경로 (./img/... 그대로)
  price          integer,                        -- 판매가 (숫자: 4200)
  discount_rate  integer,                        -- 할인율 (숫자: 35)
  unit_price     text,                           -- "(10g당 1,313원)"
  rating         numeric(2,1),                   -- 평점 4.8
  review_count   integer,                        -- 후기 수
  created_at     timestamptz not null default now()
);


-- 2) 섹션 표 : 메인 화면의 묶음 (추천 / 할인 / 선물세트 / MD / 신상품 / 베스트)
create table if not exists sections (
  key        text primary key,                   -- client, discount, gift, md, new, best
  title      text not null,                      -- 섹션 제목
  subtitle   text,                               -- 부제목
  meta       jsonb not null default '{}'::jsonb, -- MD 배너, 베스트 탭 등 섹션 전용 정보
  sort_order integer not null default 0
);


-- 3) 섹션별 상품 표 : "어느 섹션에 어떤 상품이 어떤 순서로 나오는가"
--    같은 상품이 두 섹션에 나와도 상품 표에는 1줄, 이 표에만 2줄이 생깁니다.
create table if not exists section_products (
  section_key    text    not null references sections(key)  on delete cascade,
  product_id     bigint  not null references products(id)   on delete cascade,
  sort_order     integer not null default 0,     -- 화면 순서 (베스트는 순위)
  image          text,                           -- 이 섹션에서 쓰는 이미지 (없으면 상품 기본 이미지)
  thumb_image    text,                           -- 신상품 섹션의 작은 이미지
  badge          text,                           -- BEST / NEW 등
  delivery_badge text,                           -- 무료배송
  extra_badge    text,                           -- 골라담아할인
  primary key (section_key, product_id)
);
create index if not exists idx_section_products_product on section_products(product_id);


-- 4) 상세정보 표 : 상품 상세 페이지의 내용 (지금 sub.json 모양 그대로 통째로 보관)
create table if not exists product_details (
  product_id bigint primary key references products(id) on delete cascade,
  detail     jsonb  not null,
  updated_at timestamptz not null default now()
);


-- 5) 보안 잠금 : 표마다 "읽기만 공개, 쓰기는 서버 열쇠만" 으로 설정
alter table products         enable row level security;
alter table sections         enable row level security;
alter table section_products enable row level security;
alter table product_details  enable row level security;

drop policy if exists "누구나 읽기" on products;
create policy "누구나 읽기" on products         for select to anon, authenticated using (true);

drop policy if exists "누구나 읽기" on sections;
create policy "누구나 읽기" on sections         for select to anon, authenticated using (true);

drop policy if exists "누구나 읽기" on section_products;
create policy "누구나 읽기" on section_products for select to anon, authenticated using (true);

drop policy if exists "누구나 읽기" on product_details;
create policy "누구나 읽기" on product_details  for select to anon, authenticated using (true);

-- (쓰기 규칙은 만들지 않았으므로, 서버의 service_role 열쇠로만 상품을 추가·수정·삭제할 수 있습니다.)


-- 6) 서버(service_role)가 표를 쓸 수 있게 권한 부여
--    (프로젝트 만들 때 "새 표 자동 공개"를 껐기 때문에 직접 허용해 줍니다)
grant all on table products, sections, section_products, product_details to service_role;
grant usage, select on all sequences in schema public to service_role;
