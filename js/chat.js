// chat.js — 모든 페이지 왼쪽 아래의 로봇 버튼 '올가 상담봇'
// 버튼을 누르면 채팅 창이 아래에서 살짝 떠오르며 열립니다.
// 서버(API)가 없거나 챗봇이 꺼져 있으면 버튼을 보여주지 않습니다.
// 사진 버튼(📷)을 누르면 서버의 YOLO 가 사진 속 식품을 찾고, 비슷한 상품을 추천합니다.

import { apiBase, detailUrl } from "./api.js";

const GREETING = "안녕하세요! 올가 상담봇이에요 🌿\n배송, 반품·환불, 적립금, 상품 가격 등 궁금한 점을 물어보세요.";
const SUGGESTIONS = ["배송비는 얼마예요?", "신선식품도 반품되나요?", "적립금은 어떻게 쌓여요?", "베스트 1위 상품은?"];
const MAX_LEN = 300;
const PHOTO_MAX_SIDE = 640;                        // 사진을 이 크기 이하로 줄여서 보냄 (무료 서버 부담 ↓)
const PHOTO_CHIP = "📷 사진으로 상품 찾기";

// 로봇 얼굴 아이콘 (안테나 · 얼굴 · 눈 · 웃는 입)
const ROBOT_SVG = `
<svg viewBox="0 0 48 48" aria-hidden="true" focusable="false">
  <line x1="24" y1="5" x2="24" y2="11" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/>
  <circle cx="24" cy="5" r="3" fill="currentColor"/>
  <rect x="9" y="11" width="30" height="25" rx="9" fill="currentColor"/>
  <rect x="5" y="19" width="4" height="9" rx="2" fill="currentColor"/>
  <rect x="39" y="19" width="4" height="9" rx="2" fill="currentColor"/>
  <circle class="robot-eye" cx="18.5" cy="22.5" r="3.2"/>
  <circle class="robot-eye" cx="29.5" cy="22.5" r="3.2"/>
  <path class="robot-mouth" d="M18 29.5 Q24 33.5 30 29.5" fill="none" stroke-width="2.4" stroke-linecap="round"/>
  <rect x="15" y="38" width="18" height="6" rx="3" fill="currentColor" opacity=".55"/>
</svg>`;
const CAMERA_SVG = `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 8.5A2.5 2.5 0 0 1 6.5 6h1.6l1.3-1.8c.3-.4.7-.6 1.2-.6h2.8c.5 0 .9.2 1.2.6L15.9 6h1.6A2.5 2.5 0 0 1 20 8.5v8a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 16.5z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><circle cx="12" cy="12.4" r="3.4" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>`;
const SEND_SVG = `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 12l15-7-5 15-2.6-6.2L4 12z" fill="currentColor"/></svg>`;

const history = [];   // 최근 대화 (서버에는 최근 6개만 보냄)
let busy = false;

init();

async function init() {
  const base = apiBase();
  if (base === null) return;                       // 서버 없는 배포 환경
  let status;
  try {
    const res = await fetch(`${base}/api/chat/status`);
    status = res.ok ? await res.json() : {};
    if (!status.enabled) return;
  } catch (e) {
    return;                                        // 서버가 꺼져 있으면 버튼을 띄우지 않음
  }
  // 상담봇 전용 스타일(css/chat.css)을 직접 불러오고, 다 불러온 뒤에만 버튼을 만든다
  // → 브라우저에 예전 CSS 가 남아 있어도 스타일 없는 큰 로봇이 화면에 뜨지 않음
  if (!(await loadStyles())) return;
  build(base, !!status.vision);
}

const CSS_VERSION = "20261020c";

function loadStyles() {
  return new Promise((resolve) => {
    if (document.querySelector("link[data-chat-css]")) return resolve(true);
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = new URL(`../css/chat.css?v=${CSS_VERSION}`, import.meta.url).href;  // chat.js 위치 기준
    link.dataset.chatCss = "";
    link.onload = () => resolve(true);
    link.onerror = () => resolve(false);            // 스타일을 못 불러오면 버튼도 만들지 않음
    document.head.append(link);
  });
}

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;          // 답변은 항상 글자로만 넣어 HTML 이 실행되지 않게
  return n;
}

function avatar(size) {
  const a = el("span", `chat-avatar chat-avatar--${size}`);
  a.innerHTML = ROBOT_SVG;
  return a;
}

function build(base, visionOn) {
  // ── 떠 있는 로봇 버튼 ──
  const toggle = el("button", "chat-toggle");
  toggle.type = "button";
  toggle.setAttribute("aria-label", "올가 상담봇 열기");
  toggle.setAttribute("aria-expanded", "false");
  toggle.innerHTML = `<span class="chat-toggle-robot">${ROBOT_SVG}</span><span class="chat-toggle-tip">무엇이든 물어보세요</span>`;

  // ── 채팅 창 ──
  const panel = el("section", "chat-panel");
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "올가 상담봇");
  panel.setAttribute("aria-hidden", "true");

  const head = el("header", "chat-head");
  const who = el("div", "chat-who");
  const names = el("div", "chat-names");
  names.append(el("strong", null, "올가 상담봇"));
  const status = el("span", "chat-status", "지금 바로 답변해 드려요");
  names.append(status);
  who.append(avatar("lg"), names);
  const close = el("button", "chat-close");
  close.type = "button";
  close.setAttribute("aria-label", "상담봇 닫기");
  close.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>`;
  head.append(who, close);

  const list = el("div", "chat-messages");
  list.setAttribute("aria-live", "polite");

  // 사진 고르기 (화면에는 숨겨 두고 📷 버튼이 대신 엶)
  const fileInput = el("input", "chat-file");
  fileInput.type = "file";
  fileInput.accept = "image/*";
  fileInput.hidden = true;
  fileInput.addEventListener("change", () => {
    const file = fileInput.files && fileInput.files[0];
    fileInput.value = "";                          // 같은 사진을 다시 골라도 동작하게
    if (file) sendPhoto(file);
  });

  const chips = el("div", "chat-chips");
  (visionOn ? [...SUGGESTIONS, PHOTO_CHIP] : SUGGESTIONS).forEach((q) => {
    const c = el("button", "chat-chip", q);
    c.type = "button";
    c.addEventListener("click", () => (q === PHOTO_CHIP ? fileInput.click() : send(q)));
    chips.append(c);
  });

  const form = el("form", "chat-form");
  let photoBtn = null;
  if (visionOn) {
    photoBtn = el("button", "chat-photo");
    photoBtn.type = "button";
    photoBtn.setAttribute("aria-label", "사진으로 상품 찾기");
    photoBtn.title = "사진으로 상품 찾기";
    photoBtn.innerHTML = CAMERA_SVG;
    photoBtn.addEventListener("click", () => fileInput.click());
    form.append(photoBtn);
  }
  const input = el("textarea", "chat-input");
  input.rows = 1;
  input.maxLength = MAX_LEN;
  input.placeholder = "메시지를 입력하세요";
  input.setAttribute("aria-label", "질문 입력");
  const submit = el("button", "chat-send");
  submit.type = "submit";
  submit.setAttribute("aria-label", "보내기");
  submit.innerHTML = SEND_SVG;
  form.append(input, submit);

  const foot = el("p", "chat-foot", "상담봇은 쇼핑몰 이용 안내와 상품 정보를 바탕으로 답해요");

  panel.append(head, list, chips, form, foot, fileInput);
  document.body.append(panel, toggle);

  addMessage("bot", GREETING);

  const open = (yes) => {
    panel.classList.toggle("is-open", yes);
    panel.setAttribute("aria-hidden", String(!yes));
    toggle.setAttribute("aria-expanded", String(yes));
    toggle.setAttribute("aria-label", yes ? "올가 상담봇 닫기" : "올가 상담봇 열기");
    toggle.classList.toggle("is-open", yes);
    if (yes) setTimeout(() => input.focus(), 180);
  };
  toggle.addEventListener("click", () => open(!panel.classList.contains("is-open")));
  close.addEventListener("click", () => { open(false); toggle.focus(); });
  panel.addEventListener("keydown", (e) => { if (e.key === "Escape") { open(false); toggle.focus(); } });
  form.addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(input.value); }
  });
  input.addEventListener("input", () => {           // 입력 길이에 맞춰 칸 높이 조절 (최대 3줄)
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 96) + "px";
  });

  function addMessage(who, text) {
    const bubble = el("div", `chat-msg chat-msg--${who}`, text);
    addRow(who, bubble);
    return bubble;
  }

  function addRow(who, bubble) {
    const row = el("div", `chat-row chat-row--${who}`);
    if (who === "bot") row.append(avatar("sm"));
    row.append(bubble);
    list.append(row);
    list.scrollTop = list.scrollHeight;
    return row;
  }

  function setBusy(yes) {
    busy = yes;
    submit.disabled = yes;
    if (photoBtn) photoBtn.disabled = yes;
  }

  function addTyping() {
    const row = el("div", "chat-row chat-row--bot");
    const dots = el("div", "chat-msg chat-msg--bot chat-typing");
    dots.setAttribute("aria-label", "답변을 준비하고 있어요");
    dots.innerHTML = "<span></span><span></span><span></span>";
    row.append(avatar("sm"), dots);
    list.append(row);
    list.scrollTop = list.scrollHeight;
    return row;
  }

  async function send(raw) {
    const question = (raw || "").trim().slice(0, MAX_LEN);
    if (!question || busy) return;
    setBusy(true);
    input.value = "";
    input.style.height = "auto";
    chips.hidden = true;
    addMessage("user", question);
    const typing = addTyping();

    let answer, sources = [], isError = false;
    try {
      const res = await fetch(`${base}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, history: history.slice(-6) }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "지금은 답변하기 어려워요. 잠시 후 다시 시도해 주세요.");
      answer = data.answer;
      sources = Array.isArray(data.sources) ? data.sources : [];
      history.push({ role: "user", content: question }, { role: "assistant", content: answer.slice(0, 600) });
    } catch (e) {
      answer = typeof e.message === "string" && e.message ? e.message : "지금은 답변하기 어려워요.";
      isError = true;
    } finally {
      typing.remove();
      const bubble = addMessage("bot", answer);
      if (isError) bubble.classList.add("is-error");
      if (sources.length) {                        // 벡터 검색으로 찾아 참고한 자료
        bubble.append(el("span", "chat-sources", "참고: " + sources.join(" · ")));
      }
      setBusy(false);
      input.focus();
    }
  }

  // ── 사진으로 상품 찾기: 사진 줄이기 → 서버(YOLO) → 찾은 위치 표시 + 추천 상품 ──
  async function sendPhoto(file) {
    if (busy) return;
    if (!/^image\//.test(file.type)) {
      addMessage("bot", "사진 파일만 올릴 수 있어요.").classList.add("is-error");
      return;
    }
    setBusy(true);
    chips.hidden = true;
    let dataUrl;
    try {
      dataUrl = await shrink(file);
    } catch (e) {
      addMessage("bot", "사진을 열 수 없어요. 다른 사진으로 시도해 주세요.").classList.add("is-error");
      setBusy(false);
      return;
    }
    const mine = el("div", "chat-msg chat-msg--user chat-msg--photo");
    const thumb = el("img");
    thumb.src = dataUrl;
    thumb.alt = "보낸 사진";
    mine.append(thumb);
    addRow("user", mine);
    const typing = addTyping();

    try {
      const res = await fetch(`${base}/api/vision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: dataUrl }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "지금은 사진을 확인하기 어려워요. 잠시 후 다시 시도해 주세요.");
      typing.remove();
      addRow("bot", photoResult(dataUrl, data));
      const found = data.detections.filter((d) => d.food).map((d) => d.label_ko);
      history.push(
        { role: "user", content: `[사진 검색] ${found.join(", ") || "식품 없음"}` },
        { role: "assistant", content: (data.message + " " + data.products.map((p) => p.name).join(", ")).slice(0, 600) },
      );
    } catch (e) {
      typing.remove();
      const msg = typeof e.message === "string" && e.message ? e.message : "지금은 사진을 확인하기 어려워요.";
      addMessage("bot", msg).classList.add("is-error");
    } finally {
      setBusy(false);
    }
  }

  function photoResult(dataUrl, data) {
    const bubble = el("div", "chat-msg chat-msg--bot chat-vision");
    const figure = el("div", "chat-vision-figure");
    const img = el("img");
    img.src = dataUrl;
    img.alt = "YOLO 가 찾은 물체 표시";
    figure.append(img);
    data.detections.forEach((d) => {                // 찾은 위치를 비율(0~1)로 받아 네모로 표시
      const [x1, y1, x2, y2] = d.box;
      const box = el("span", "chat-vision-box" + (d.food ? " is-food" : ""));
      box.style.left = `${x1 * 100}%`;
      box.style.top = `${y1 * 100}%`;
      box.style.width = `${(x2 - x1) * 100}%`;
      box.style.height = `${(y2 - y1) * 100}%`;
      box.append(el("em", null, `${d.label_ko} ${Math.round(d.score * 100)}%`));
      figure.append(box);
    });
    bubble.append(figure, el("p", "chat-vision-text", data.message));
    if (data.products.length) {
      const cards = el("div", "chat-products");
      data.products.forEach((p) => {
        const a = el("a", "chat-product");
        a.href = detailUrl(p);
        const pic = el("img");
        pic.src = p.image || "";
        pic.alt = "";
        pic.loading = "lazy";
        const info = el("span", "chat-product-info");
        info.append(el("strong", null, p.name), el("span", null, p.price || ""));
        a.append(pic, info);
        cards.append(a);
      });
      bubble.append(cards);
    }
    bubble.append(el("span", "chat-sources", "YOLO 물체 인식 결과 · 일반 물체 80종 기준"));
    return bubble;
  }
}

/** 사진을 긴 쪽 640px 이하 JPEG 로 줄임 (휴대폰 사진의 회전 정보도 반영) */
async function shrink(file) {
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  const scale = Math.min(1, PHOTO_MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  if (bitmap.close) bitmap.close();
  return canvas.toDataURL("image/jpeg", 0.85);
}
