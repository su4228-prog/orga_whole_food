-- ============================================================
-- 회원 표 만들기 (회원가입 · 로그인 · 관리자 권한)
-- 사용법: Supabase 왼쪽 메뉴 'SQL Editor' → New query → 이 내용을 통째로 붙여넣고 Run
-- 여러 번 실행해도 안전합니다 (이미 있으면 건너뜀).
-- ============================================================

create table if not exists users (
  id            bigint generated always as identity primary key,
  login_id      text not null unique
                check (login_id ~ '^[a-z0-9]{4,20}$'),          -- 아이디: 영문 소문자 · 숫자 4~20자
  password_hash text not null,                                 -- bcrypt 해시 (비밀번호 원문은 저장하지 않음)
  name          text not null check (char_length(name) between 1 and 20),
  role          text not null default 'user'
                check (role in ('user', 'admin')),             -- 관리자 권한은 DB 에서만 바꿀 수 있음
  created_at    timestamptz not null default now(),
  last_login_at timestamptz
);

-- 관리자 작업 기록에 "누가 했는지" 남기기
alter table admin_action_logs add column if not exists actor text;

-- 보안: 회원 표는 서버(service_role)만 읽고 씁니다. 브라우저(anon)에서는 접근 불가.
alter table users enable row level security;
grant all on table users to service_role;
grant usage, select on all sequences in schema public to service_role;
