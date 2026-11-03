// auth.js — 로그인 상태 유지 (모든 페이지 공통)
//
// 로그인 성공 → 서버가 출입증(JWT)을 HttpOnly 쿠키로 저장 (화면의 스크립트는 읽을 수 없음)
//              화면은 헤더 표시에 필요한 회원 정보(이름 · 역할 · 만료 시각)만 localStorage 에 보관
// 요청할 때 → 쿠키가 자동으로 함께 감 · 데이터를 바꾸는 요청에는 X-Requested-With 머리말
// 로그아웃 → 서버가 쿠키 삭제 + 화면의 회원 정보 삭제
// 만료 시각이 지났거나 서버가 출입증을 거절하면 자동으로 로그아웃 상태가 됩니다.

import { apiBase } from "./api.js";

const USER_KEY = "orga_user";

function read(key) {
  try { return localStorage.getItem(key); } catch (e) { return null; }
}

function write(key, value) {
  try { value == null ? localStorage.removeItem(key) : localStorage.setItem(key, value); } catch (e) { /* 저장 불가 환경 */ }
}

write("orga_token", null);                          // 예전 방식(localStorage 토큰)으로 남은 값 정리

/** 로그인한 회원 정보 { id, login_id, name, role, expires_at } — 없거나 만료면 null */
export function getUser() {
  let user = null;
  try { user = JSON.parse(read(USER_KEY) || "null"); } catch (e) { user = null; }
  if (!user) return null;
  if (!user.expires_at || user.expires_at * 1000 <= Date.now()) {
    write(USER_KEY, null);
    return null;
  }
  return user;
}

/** 로그인 · 가입 응답 { user, expires_at } 저장 (출입증은 서버가 쿠키로 따로 저장) */
export function saveSession(data) {
  write(USER_KEY, JSON.stringify({ ...data.user, expires_at: data.expires_at }));
}

export async function clearSession() {
  write(USER_KEY, null);
  const base = apiBase();
  if (base === null) return;
  try {
    await fetch(`${base}/api/auth/logout`, { method: "POST", credentials: "include", headers: authHeaders() });
  } catch (e) { /* 서버가 잠시 안 되어도 화면은 로그아웃 상태 */ }
}

/** 서버 요청에 붙일 머리말 — 쿠키는 브라우저가 자동으로 보냄 */
export function authHeaders() {
  return { "X-Requested-With": "orga" };
}

/** 로그인 뒤 돌아갈 주소 — 이 사이트 안의 페이지만 허용 */
export function safeNext(next) {
  return /^(index|sub|admin)\.html([?#][\w=&%.-]*)?$/.test(next || "") ? next : "index.html";
}

function currentPage() {
  const path = location.pathname.split("/").pop() || "index.html";
  return path + location.search;
}

// ───────────────────────── 헤더의 회원 메뉴 ─────────────────────────
function link(text, href) {
  const a = document.createElement("a");
  a.href = href;
  a.textContent = text;
  return a;
}

export function renderMemberLinks() {
  const nav = document.querySelector(".member-links");
  if (!nav) return;
  const user = getUser();
  const items = [];
  if (user) {
    const hello = document.createElement("span");
    hello.className = "member-hello";
    const name = document.createElement("b");
    name.textContent = user.name;
    hello.append(name, "님");
    const out = link("로그아웃", "#");
    out.addEventListener("click", async (e) => {
      e.preventDefault();
      await clearSession();
      if (/admin\.html$/.test(location.pathname)) location.href = "index.html";
      else renderMemberLinks();
    });
    items.push(hello, out, link("고객센터", "#"));
    if (user.role === "admin") items.push(link("관리자", "admin.html"));
  } else {
    items.push(link("로그인", `login.html?next=${encodeURIComponent(currentPage())}`),
               link("회원가입", "signup.html"), link("고객센터", "#"));
  }
  nav.replaceChildren(...items);
}

/** 서버에 출입증이 아직 유효한지 확인하고 이름 · 권한을 최신으로 맞춤 */
export async function refreshUser() {
  const base = apiBase();
  if (base === null || !getUser()) return getUser();
  try {
    const res = await fetch(`${base}/api/auth/me`, { credentials: "include" });
    if (res.status === 401) {
      write(USER_KEY, null);
      return null;
    }
    if (res.ok) {
      const me = await res.json();
      const user = getUser();
      if (user) write(USER_KEY, JSON.stringify({ ...user, ...me }));
    }
  } catch (e) { /* 서버가 잠시 안 되면 저장된 정보 그대로 */ }
  return getUser();
}

// 쇼핑몰 페이지(헤더에 회원 메뉴가 있는 곳)에서는 바로 그리고, 서버 확인 후 한 번 더 그림
if (document.querySelector(".member-links")) {
  renderMemberLinks();
  refreshUser().then(renderMemberLinks);
}
