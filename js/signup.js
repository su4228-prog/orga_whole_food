// signup.js — 회원가입 화면 (signup.html)
// 입력 확인 → 서버에 가입 요청 → 가입과 동시에 로그인 → 메인으로 이동

import { apiBase } from "./api.js";
import { getUser, saveSession } from "./auth.js";

const base = apiBase();
const $ = (id) => document.getElementById(id);
const ID_RULE = /^[a-z0-9]{4,20}$/;
const PW_RULE = /^(?=.*[A-Za-z])(?=.*\d).{8,64}$/;
let checkedId = null;                               // 중복 확인을 통과한 아이디

if (getUser()) location.replace("index.html");

// 비밀번호 보기
document.querySelectorAll("[data-eye]").forEach((b) => {
  b.addEventListener("click", () => {
    const input = $(b.dataset.eye);
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    b.setAttribute("aria-pressed", String(show));
  });
});

// 아이디: 입력하면 다시 확인하도록
$("suId").addEventListener("input", (e) => {
  checkedId = null;
  if (e.isComposing) return;                         // 한글 입력 중에는 글자를 건드리지 않음
  const v = $("suId").value;
  if (/[^A-Za-z0-9]/.test(v)) {                      // 지우지 않고 안내만 (한/영 키가 한글일 때 입력이 안 되는 것처럼 보이지 않게)
    hint("idHint", "아이디는 영문과 숫자만 쓸 수 있어요. 한/영 키를 눌러 영문으로 바꿔 주세요.", "error");
    return;
  }
  if (v !== v.toLowerCase()) $("suId").value = v.toLowerCase();
  hint("idHint", "영문 소문자와 숫자로 4~20자");
});
$("suId").addEventListener("blur", () => { if ($("suId").value) checkId(); });
$("checkIdBtn").addEventListener("click", checkId);

async function checkId() {
  const id = $("suId").value;
  if (!ID_RULE.test(id)) return hint("idHint", "영문 소문자와 숫자로 4~20자로 입력해 주세요.", "error");
  if (base === null) return hint("idHint", "회원가입은 서버가 켜진 주소에서만 할 수 있어요.", "error");
  try {
    const res = await fetch(`${base}/api/auth/check-id?login_id=${encodeURIComponent(id)}`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail);          // 서버 · DB 오류를 '이미 사용 중'으로 착각하지 않게
    if (data.available) {
      checkedId = id;
      hint("idHint", "사용할 수 있는 아이디예요.", "ok");
    } else {
      hint("idHint", "이미 사용 중인 아이디예요.", "error");
    }
  } catch (e) {
    hint("idHint", "확인하지 못했어요. 잠시 후 다시 시도해 주세요.", "error");
  }
}

// 비밀번호 규칙 · 일치 확인
["suPw", "suPw2"].forEach((id) => $(id).addEventListener("input", checkPw));
function checkPw() {
  const pw = $("suPw").value, pw2 = $("suPw2").value, id = $("suId").value;
  if (!pw) hint("pwHint", "영문과 숫자를 섞어 8자 이상 (아이디는 넣을 수 없어요)");
  else if (!PW_RULE.test(pw)) hint("pwHint", "영문과 숫자를 섞어 8자 이상으로 입력해 주세요.", "error");
  else if (id && pw.toLowerCase().includes(id)) hint("pwHint", "비밀번호에 아이디를 넣을 수 없어요.", "error");
  else hint("pwHint", "사용할 수 있는 비밀번호예요.", "ok");
  if (pw2) hint("pw2Hint", pw === pw2 ? "비밀번호가 같아요." : "비밀번호가 서로 달라요.", pw === pw2 ? "ok" : "error");
  else hint("pw2Hint", "");
}

// 약관 전체 동의
const items = [...document.querySelectorAll(".agree-item")];
$("agreeAll").addEventListener("change", (e) => items.forEach((x) => { x.checked = e.target.checked; }));
items.forEach((x) => x.addEventListener("change", () => { $("agreeAll").checked = items.every((i) => i.checked); }));

// 가입
$("signupForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const login_id = $("suId").value, password = $("suPw").value, name = $("suName").value.trim();
  if (!ID_RULE.test(login_id)) return fail("아이디를 확인해 주세요.", "suId");
  if (checkedId !== login_id) {
    await checkId();
    if (checkedId !== login_id) return fail("아이디 중복 확인을 해 주세요.", "suId");
  }
  if (!PW_RULE.test(password) || password.toLowerCase().includes(login_id)) return fail("비밀번호 규칙을 확인해 주세요.", "suPw");
  if (password !== $("suPw2").value) return fail("비밀번호 확인이 서로 달라요.", "suPw2");
  if (!name) return fail("이름을 입력해 주세요.", "suName");
  if (!items.every((i) => i.checked)) return fail("필수 약관에 동의해 주세요.");

  const btn = $("signupBtn");
  btn.disabled = true;
  try {
    const res = await fetch(`${base}/api/auth/signup`, {
      method: "POST",
      credentials: "include",                       // 출입증 쿠키 받기
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ login_id, password, name }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "가입하지 못했어요. 잠시 후 다시 시도해 주세요.");
    saveSession(data);
    location.href = "index.html";
  } catch (err) {
    fail(err.message);
  } finally {
    btn.disabled = false;
  }
});

function hint(id, text, kind) {
  const el = $(id);
  el.textContent = text;
  el.className = "hint" + (kind === "ok" ? " is-ok" : kind === "error" ? " is-error" : "");
}

function fail(text, inputId) {
  const msg = $("signupMsg");
  msg.textContent = text;
  if (inputId) $(inputId).focus();
}
