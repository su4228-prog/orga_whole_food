// login.js — 로그인 화면 (login.html)
// 로그인 성공 → 출입증 저장(auth.js) → 원래 보던 페이지로 이동

import { apiBase } from "./api.js";
import { getUser, safeNext, saveSession } from "./auth.js";

const SAVED_ID_KEY = "orga_saved_id";
const base = apiBase();
const next = safeNext(new URLSearchParams(location.search).get("next"));
const form = document.getElementById("loginForm");
const idInput = document.getElementById("loginId");
const pwInput = document.getElementById("loginPw");
const msg = document.getElementById("loginMsg");
const btn = document.getElementById("loginBtn");
const saveId = document.getElementById("saveId");

if (getUser()) location.replace(next);           // 이미 로그인했으면 바로 이동

bindEyes();
bindSoon();

try {
  const saved = localStorage.getItem(SAVED_ID_KEY);
  if (saved) {
    idInput.value = saved;
    saveId.checked = true;
    pwInput.focus();
  } else {
    idInput.focus();
  }
} catch (e) { idInput.focus(); }

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const login_id = idInput.value.trim().toLowerCase();
  const password = pwInput.value;
  [idInput, pwInput].forEach((x) => x.classList.remove("is-error"));
  if (!login_id) return fail("아이디를 입력해 주세요.", idInput);
  if (!password) return fail("비밀번호를 입력해 주세요.", pwInput);
  if (base === null) return fail("로그인은 서버가 켜진 주소에서만 할 수 있어요.");

  btn.disabled = true;
  msg.textContent = "";
  try {
    const res = await fetch(`${base}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ login_id, password }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "로그인하지 못했어요. 잠시 후 다시 시도해 주세요.");
    saveSession(data);
    try {
      saveId.checked ? localStorage.setItem(SAVED_ID_KEY, login_id) : localStorage.removeItem(SAVED_ID_KEY);
    } catch (err) { /* 저장 불가 환경 */ }
    location.href = next;
  } catch (err) {
    fail(err.message, pwInput);
    pwInput.select();
  } finally {
    btn.disabled = false;
  }
});

function fail(text, input) {
  msg.textContent = text;
  if (input) {
    input.classList.add("is-error");
    input.focus();
  }
}

function bindEyes() {
  document.querySelectorAll("[data-eye]").forEach((b) => {
    b.addEventListener("click", () => {
      const input = document.getElementById(b.dataset.eye);
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      b.setAttribute("aria-pressed", String(show));
      b.setAttribute("aria-label", show ? "비밀번호 숨기기" : "비밀번호 보기");
    });
  });
}

function bindSoon() {
  const easy = document.getElementById("easyMsg");
  document.querySelectorAll("[data-soon]").forEach((b) => {
    b.addEventListener("click", () => {
      easy.textContent = `${b.dataset.soon}는 준비 중이에요. 일반 회원가입으로 가입해 주세요.`;
    });
  });
}
