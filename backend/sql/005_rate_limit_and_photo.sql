-- ============================================================
-- ① 사용 횟수 제한 기록 (상담봇 · 사진 검색 · 로그인 · 가입 · 관리자 AI 분석)
-- ② 상품 사진 특징 (사진으로 같은 상품 찾기)
-- 사용법: Supabase 왼쪽 메뉴 'SQL Editor' → New query → 이 내용을 통째로 붙여넣고 Run
-- 여러 번 실행해도 안전합니다.
--
-- 서버 메모리가 아니라 DB 에 세기 때문에 서버가 다시 켜져도 횟수가 유지됩니다.
-- ============================================================

create table if not exists rate_limit_hits (
  id         bigint generated always as identity primary key,
  bucket     text not null,                     -- chat · vision · login · signup · analyze
  key        text not null,                     -- 방문자 주소
  created_at timestamptz not null default now()
);

create index if not exists rate_limit_hits_key_idx on rate_limit_hits (bucket, key, created_at desc);
create index if not exists rate_limit_hits_day_idx on rate_limit_hits (bucket, created_at desc);

-- 한 번에 확인하고 기록하기
-- 반환: 'ok' (통과) · 'day' (사이트 전체 하루 한도) · 'user:초' (한 사람 한도, 다시 쓸 수 있을 때까지 남은 초)
create or replace function rate_limit_hit(
  p_bucket     text,
  p_key        text,
  p_window_sec int,
  p_per_user   int,
  p_per_day    int
)
returns text
language plpgsql
set search_path = public
as $$
declare
  day_count  int;
  user_count int;
  oldest     timestamptz;
begin
  -- 같은 사람의 요청이 동시에 와도 한 번씩 차례로 세도록 잠금
  perform pg_advisory_xact_lock(hashtext(p_bucket || ':' || p_key));

  -- 이틀 지난 기록은 정리
  delete from rate_limit_hits where bucket = p_bucket and created_at < now() - interval '2 days';

  select count(*) into day_count
    from rate_limit_hits
   where bucket = p_bucket and created_at >= date_trunc('day', now());
  if day_count >= p_per_day then
    return 'day';
  end if;

  select count(*), min(created_at) into user_count, oldest
    from rate_limit_hits
   where bucket = p_bucket and key = p_key
     and created_at > now() - make_interval(secs => p_window_sec);
  if user_count >= p_per_user then
    return 'user:' || greatest(1, ceil(extract(epoch from (oldest + make_interval(secs => p_window_sec) - now()))))::int;
  end if;

  insert into rate_limit_hits (bucket, key) values (p_bucket, p_key);
  return 'ok';
end;
$$;

-- 보안: 서버(service_role)만 사용
alter table rate_limit_hits enable row level security;
grant all on table rate_limit_hits to service_role;
grant usage, select on all sequences in schema public to service_role;
grant execute on function rate_limit_hit(text, text, int, int, int) to service_role;
revoke execute on function rate_limit_hit(text, text, int, int, int) from anon, authenticated, public;


-- ============================================================
-- ② 상품 사진 특징 — YOLO 분류 모델이 뽑은 숫자 1280개 (scripts/build_photo_vectors.py 가 채움)
--    올린 사진의 특징과 비교해 같은 올가 상품을 찾습니다.
-- ============================================================
create table if not exists product_photo_vectors (
  product_id bigint primary key references products(id) on delete cascade,
  image      text   not null,                   -- 특징을 뽑은 사진 경로
  vector     real[] not null,                   -- 길이 1 로 맞춘 특징 1280개
  updated_at timestamptz not null default now()
);

alter table product_photo_vectors enable row level security;
grant all on table product_photo_vectors to service_role;
