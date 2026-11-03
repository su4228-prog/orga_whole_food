// admin.js — 관리자 AI 상품등록 · 상품 관리
//
// 흐름: 관리자 계정으로 로그인(login.html, JWT) → 사진 업로드 → AI 분석(YOLO + OpenAI Vision)
//       → 입력칸 자동 채움 → 관리자가 확인 후 등록 → 목록 · 기록 갱신
// role=admin 계정만 들어올 수 있습니다. 모든 글자는 textContent 로 넣어 HTML 이 실행되지 않게 합니다.

import { apiBase, detailUrl } from "./api.js";
import { clearSession, getToken, refreshUser } from "./auth.js";

const PHOTO_MAX_SIDE = 1200;
const $ = (id) => document.getElementById(id);

const base = apiBase();
const state = { image: null, fileName: "", analysisId: null, page: 1, q: "",
                categories: [], storages: [], highlight: null };

init();

// ───────────────────────── 시작 · 권한 확인 ─────────────────────────
async function init() {
  if (base === null) return show("noServer");
  let status;
  try {
    const res = await fetch(`${base}/api/admin/status`);
    status = await res.json();
  } catch (e) {
    return show("noServer");
  }
  state.categories = status.categories || [];
  state.storages = status.storages || [];
  fillSelect($("categorySelect"), state.categories, "분류 선택");
  fillSelect($("storageSelect"), state.storages);
  if (!status.enabled) return gate("로그인 기능이 꺼져 있어요", "서버에 JWT_SECRET 이 설정되지 않았어요.");

  const user = await refreshUser();               // 서버에 출입증 확인 + 최신 권한
  if (!user) return gate("관리자 계정으로 로그인해 주세요", "");
  if (user.role !== "admin") return gate("관리자 권한이 없는 계정이에요", `${user.name}님 계정은 일반 회원이에요. 관리자 계정으로 다시 로그인해 주세요.`, true);
  bindEvents();
  enterApp();
}

function show(id) {
  ["noServer", "loginCard", "adminApp"].forEach((x) => { $(x).hidden = x !== id; });
  $("logoutBtn").hidden = id !== "adminApp";
}

/** 들어올 수 없을 때 안내 (switchAccount 면 로그아웃하고 다른 계정으로) */
function gate(title, message, switchAccount) {
  show("loginCard");
  $("gateTitle").textContent = title;
  setMsg($("loginMsg"), message, !!message);
  const link = $("gateLink");
  link.textContent = switchAccount ? "다른 계정으로 로그인" : "로그인하러 가기";
  link.onclick = switchAccount ? () => clearSession() : null;
}

function logout() {
  clearSession();
  location.href = "login.html?next=admin.html";
}

async function enterApp() {
  show("adminApp");
  await Promise.all([loadProducts(1), loadLogs()]);
}

/** 서버 호출 — 출입증을 붙이고, 만료 · 권한 없음이면 안내 화면으로 */
async function api(path, { method = "GET", body } = {}) {
  const res = await fetch(`${base}${path}`, {
    method,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken() || ""}` },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401) {
    clearSession();
    gate("다시 로그인해 주세요", data.detail || "로그인 시간이 끝났어요.");
    throw new Error(data.detail || "로그인이 필요해요.");
  }
  if (res.status === 403) {
    gate("관리자 권한이 없는 계정이에요", data.detail || "", true);
    throw new Error(data.detail || "관리자만 할 수 있어요.");
  }
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "요청을 처리하지 못했어요.");
  return data;
}

function bindEvents() {
  $("logoutBtn").addEventListener("click", logout);

  // 사진 고르기 · 끌어 놓기
  const drop = $("dropzone");
  $("photoInput").addEventListener("change", (e) => { const f = e.target.files[0]; e.target.value = ""; if (f) pickPhoto(f); });
  drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("photoInput").click(); } });
  ["dragenter", "dragover"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.add("is-over"); }));
  ["dragleave", "drop"].forEach((t) => drop.addEventListener(t, () => drop.classList.remove("is-over")));
  drop.addEventListener("drop", (e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) pickPhoto(f); });

  $("analyzeBtn").addEventListener("click", analyze);
  $("productForm").addEventListener("submit", saveProduct);
  $("searchForm").addEventListener("submit", (e) => { e.preventDefault(); state.q = $("searchInput").value.trim(); loadProducts(1); });
  $("reloadLogs").addEventListener("click", loadLogs);
}

// ───────────────────────── 1. 사진 + AI 분석 ─────────────────────────
async function pickPhoto(file) {
  if (!/^image\//.test(file.type)) return showAi("사진 파일만 올릴 수 있어요.", true);
  try {
    state.image = await shrink(file);
  } catch (e) {
    return showAi("사진을 열 수 없어요. 다른 사진으로 시도해 주세요.", true);
  }
  state.fileName = file.name;
  state.analysisId = null;
  $("photoPreview").src = state.image;
  $("photoFigure").querySelectorAll(".yolo-box").forEach((b) => b.remove());
  $("photoFigure").hidden = false;
  $("dropEmpty").hidden = true;
  $("fileName").textContent = file.name;
  $("analyzeBtn").disabled = false;
  $("aiResult").hidden = true;
}

async function analyze() {
  if (!state.image) return;
  const btn = $("analyzeBtn");
  btn.disabled = true;
  btn.textContent = "⏳ AI가 사진을 분석하고 있어요…";
  try {
    const data = await api("/api/admin/analyze", { method: "POST", body: { image: state.image, file_name: state.fileName } });
    state.analysisId = data.analysis_id;
    drawBoxes(data.detections);
    fillForm(data.result);
    const r = data.result;
    const yolo = data.detections.map((d) => `${d.label_ko} ${Math.round(d.score * 100)}%`).join(", ") || "찾은 물체 없음";
    const box = $("aiResult");
    box.replaceChildren(
      line("YOLO 물체 인식", yolo),
      line("OpenAI Vision 추천", `${r.name || "-"} · ${r.price ? r.price.toLocaleString("ko-KR") + "원" : "가격 미정"} · ${r.category} · ${r.storage}`),
      line("근거", r.note || "-"),
      line("걸린 시간", `${(data.elapsed_ms / 1000).toFixed(1)}초 · 기록 번호 ${data.analysis_id ?? "-"}`),
    );
    box.classList.remove("is-error");
    box.hidden = false;
    loadLogs();
  } catch (err) {
    showAi(err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "✨ AI로 상품 정보 자동 완성";
  }
}

function line(label, text) {
  const p = el("div");
  p.append(el("strong", null, `${label}: `), document.createTextNode(text));
  return p;
}

function showAi(text, isError) {
  const box = $("aiResult");
  box.textContent = text;
  box.classList.toggle("is-error", !!isError);
  box.hidden = false;
}

function drawBoxes(detections) {
  const fig = $("photoFigure");
  fig.querySelectorAll(".yolo-box").forEach((b) => b.remove());
  detections.forEach((d) => {
    const [x1, y1, x2, y2] = d.box;
    const b = el("span", "yolo-box" + (d.food ? " is-food" : ""));
    Object.assign(b.style, { left: `${x1 * 100}%`, top: `${y1 * 100}%`, width: `${(x2 - x1) * 100}%`, height: `${(y2 - y1) * 100}%` });
    b.append(el("em", null, `${d.label_ko} ${Math.round(d.score * 100)}%`));
    fig.append(b);
  });
}

function fillForm(r) {
  const f = $("productForm");
  const set = (name, value) => {
    if (value == null || value === "") return;
    f.elements[name].value = value;
    f.elements[name].classList.add("ai-filled");
  };
  set("name", r.name);
  set("price", r.price);
  set("category", r.category);
  set("storage", r.storage);
  set("description", r.description);
}

// ───────────────────────── 2. 등록 ─────────────────────────
async function saveProduct(e) {
  e.preventDefault();
  const msg = $("saveMsg");
  if (!state.image) return setMsg(msg, "먼저 상품 사진을 올려 주세요.", true);
  const f = e.target;
  const body = formValues(f);
  body.image = state.image;
  body.analysis_id = state.analysisId;
  const btn = $("saveBtn");
  btn.disabled = true;
  setMsg(msg, "등록하고 있어요…");
  try {
    const p = await api("/api/admin/products", { method: "POST", body });
    msg.replaceChildren(document.createTextNode(`✅ ${p.name} 등록 완료 (상품 번호 ${p.id}) · `));
    const a = el("a", null, "상세 페이지 보기");
    a.href = detailUrl(p);
    a.target = "_blank";
    a.rel = "noopener";
    msg.append(a);
    msg.className = "form-msg is-ok";
    resetPhoto(f);
    state.q = "";
    $("searchInput").value = "";
    state.highlight = p.id;
    await Promise.all([loadProducts(1), loadLogs()]);
  } catch (err) {
    setMsg(msg, err.message, true);
  } finally {
    btn.disabled = false;
  }
}

function formValues(f) {
  const v = (n) => f.elements[n].value.trim();
  return {
    name: v("name"),
    price: Number(v("price")),
    discount_rate: v("discount_rate") ? Number(v("discount_rate")) : null,
    category: v("category"),
    storage: v("storage") || null,
    description: v("description") || null,
  };
}

function resetPhoto(f) {
  f.reset();
  f.querySelectorAll(".ai-filled").forEach((x) => x.classList.remove("ai-filled"));
  state.image = null;
  state.analysisId = null;
  $("photoFigure").hidden = true;
  $("dropEmpty").hidden = false;
  $("fileName").textContent = "";
  $("analyzeBtn").disabled = true;
  $("aiResult").hidden = true;
}

// ───────────────────────── 3. 목록 · 검색 · 페이지 · 수정 · 삭제 ─────────────────────────
async function loadProducts(page) {
  try {
    const data = await api(`/api/admin/products?page=${page}&q=${encodeURIComponent(state.q)}`);
    state.page = data.page;
    $("totalText").textContent = `총 ${data.total}개${data.q ? ` · '${data.q}' 검색` : ""}`;
    const rows = data.items.map(viewRow);
    if (!rows.length) {
      const tr = el("tr", "empty-row");
      const td = el("td", null, data.q ? "검색 결과가 없어요." : "상품이 없어요.");
      td.colSpan = 9;
      tr.append(td);
      rows.push(tr);
    }
    $("productRows").replaceChildren(...rows);
    renderPager(data.page, data.pages);
    state.highlight = null;
  } catch (err) {
    const tr = el("tr", "empty-row");
    const td = el("td", null, err.message);
    td.colSpan = 9;
    tr.append(td);
    $("productRows").replaceChildren(tr);
  }
}

function viewRow(p) {
  const tr = el("tr", p.id === state.highlight ? "row-new" : null);
  const img = el("img");
  img.src = p.image || "";
  img.alt = "";
  img.loading = "lazy";
  const name = el("td", "name-cell");
  const link = el("a", null, p.name);
  link.href = detailUrl(p);
  link.target = "_blank";
  link.rel = "noopener";
  name.append(link);
  if (p.description) name.append(el("small", null, p.description));

  const kind = el("td");
  kind.append(p.source === "admin" ? el("span", "tag is-admin", "관리자 등록") : el("span", "tag", "원본"));
  if (p.on_main) kind.append(" ", el("span", "tag is-main", "메인 진열"));

  const actions = el("td");
  const wrap = el("div", "actions");
  const edit = button("수정", () => tr.replaceWith(editRow(p)));
  const del = button("삭제", () => removeProduct(p), "btn-danger");
  if (p.on_main) {
    del.disabled = true;
    del.title = "메인 화면에 진열된 원본 상품은 삭제할 수 없어요";
  }
  wrap.append(edit, del);
  actions.append(wrap);

  tr.append(cell(img), el("td", null, String(p.id)), name, el("td", null, p.category || "-"),
            el("td", null, p.storage || "-"), el("td", null, p.price_text || "-"),
            el("td", null, p.discount_text || "-"), kind, actions);
  return tr;
}

function editRow(p) {
  const tr = el("tr");
  const name = input("text", p.name, { maxLength: 100 });
  const price = input("number", p.price ?? "", { min: 100, max: 10000000, step: 10 });
  const disc = input("number", p.discount_rate ?? "", { min: 0, max: 90 });
  const cat = el("select");
  fillSelect(cat, state.categories);
  cat.value = p.category || "기타";
  const sto = el("select");
  const storages = p.storage && !state.storages.includes(p.storage) ? [p.storage, ...state.storages] : state.storages;
  fillSelect(sto, storages, "-");
  sto.value = p.storage || "";

  const img = el("img");
  img.src = p.image || "";
  img.alt = "";
  const msg = el("small", "form-msg");
  const save = button("저장", async () => {
    const changes = {};
    const want = { name: name.value.trim(), price: Number(price.value), discount_rate: disc.value ? Number(disc.value) : 0,
                   category: cat.value, storage: sto.value || null };
    Object.entries(want).forEach(([k, v]) => { if ((p[k] ?? (k === "discount_rate" ? 0 : null)) !== v) changes[k] = v; });
    if (!Object.keys(changes).length) return tr.replaceWith(viewRow(p));
    save.disabled = true;
    try {
      const updated = await api(`/api/admin/products/${p.id}`, { method: "PATCH", body: changes });
      state.highlight = updated.id;
      tr.replaceWith(viewRow(updated));
      loadLogs();
    } catch (err) {
      setMsg(msg, err.message, true);
      save.disabled = false;
    }
  }, "btn-green-text");
  const cancel = button("취소", () => tr.replaceWith(viewRow(p)));
  const wrap = el("div", "actions");
  wrap.append(save, cancel);
  const nameTd = el("td");
  nameTd.append(name, msg);
  const actions = el("td");
  actions.append(wrap);
  tr.append(cell(img), el("td", null, String(p.id)), nameTd, cell(cat), cell(sto), cell(price), cell(disc),
            el("td", null, p.source === "admin" ? "관리자 등록" : "원본"), actions);
  setTimeout(() => name.focus(), 0);
  return tr;
}

async function removeProduct(p) {
  if (!confirm(`'${p.name}' 상품을 삭제할까요?\n삭제하면 되돌릴 수 없어요. (작업 기록에는 남습니다)`)) return;
  try {
    await api(`/api/admin/products/${p.id}`, { method: "DELETE" });
    await Promise.all([loadProducts(state.page), loadLogs()]);
  } catch (err) {
    alert(err.message);
  }
}

function renderPager(page, pages) {
  const nav = $("pager");
  const items = [];
  const go = (n, label, current) => {
    const b = button(label, () => loadProducts(n));
    if (current) b.setAttribute("aria-current", "page");
    if (n < 1 || n > pages) b.disabled = true;
    return b;
  };
  items.push(go(page - 1, "‹ 이전"));
  const start = Math.max(1, Math.min(page - 2, pages - 4));
  for (let n = start; n <= Math.min(pages, start + 4); n++) items.push(go(n, String(n), n === page));
  items.push(go(page + 1, "다음 ›"));
  nav.replaceChildren(...items);
}

// ───────────────────────── 4. 기록 ─────────────────────────
const ACT = { create: "등록", update: "수정", delete: "삭제" };

async function loadLogs() {
  try {
    const data = await api("/api/admin/logs");
    $("actionLogs").replaceChildren(...listOrEmpty(data.actions.map((a) => {
      const li = el("li");
      li.append(el("span", `act act-${a.action}`, ACT[a.action] || a.action),
                document.createTextNode(`${a.product_name || ""} (#${a.product_id ?? "-"})`));
      const detail = describe(a);
      if (detail) li.append(el("div", null, detail));
      li.append(el("time", null, when(a.created_at) + (a.actor ? ` · ${a.actor}` : "")));
      return li;
    }), "아직 작업 기록이 없어요."));
    $("analysisLogs").replaceChildren(...listOrEmpty(data.analyses.map((x) => {
      const li = el("li");
      const r = x.result || {};
      li.append(el("strong", null, r.name || "(이름 추천 없음)"),
                el("div", null, `${r.price ? r.price.toLocaleString("ko-KR") + "원" : "가격 미정"} · ${r.category || "-"} · ${r.storage || "-"}`),
                el("div", null, "YOLO: " + ((x.yolo || []).map((d) => d.label_ko).join(", ") || "없음")),
                el("time", null, `${when(x.created_at)} · ${x.file_name || ""} · ${((x.elapsed_ms || 0) / 1000).toFixed(1)}초${x.product_id ? ` · 상품 #${x.product_id} 등록됨` : ""}`));
      return li;
    }), "아직 분석 기록이 없어요."));
  } catch (err) {
    $("actionLogs").replaceChildren(el("li", "empty", err.message));
  }
}

function describe(a) {
  if (a.action !== "update") return "";
  const labels = { name: "상품명", price: "판매가", discount_rate: "할인율", category: "분류", storage: "보관", description: "설명" };
  return Object.entries(a.detail || {}).map(([k, v]) => `${labels[k] || k}: ${v.before ?? "-"} → ${v.after ?? "-"}`).join(" · ");
}

function listOrEmpty(items, emptyText) {
  return items.length ? items : [el("li", "empty", emptyText)];
}

function when(iso) {
  return iso ? new Date(iso).toLocaleString("ko-KR", { dateStyle: "short", timeStyle: "short" }) : "";
}

// ───────────────────────── 작은 도구 ─────────────────────────
function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

function cell(child) {
  const td = el("td");
  td.append(child);
  return td;
}

function button(label, onClick, extra) {
  const b = el("button", "btn btn-small" + (extra ? ` ${extra}` : ""), label);
  b.type = "button";
  b.addEventListener("click", onClick);
  return b;
}

function input(type, value, attrs = {}) {
  const i = el("input");
  i.type = type;
  i.value = value;
  Object.assign(i, attrs);
  return i;
}

function fillSelect(select, values, placeholder) {
  const opts = values.map((v) => { const o = el("option", null, v); o.value = v; return o; });
  if (placeholder) {
    const o = el("option", null, placeholder);
    o.value = "";
    opts.unshift(o);
  }
  select.replaceChildren(...opts);
}

function setMsg(node, text, isError) {
  node.textContent = text;
  node.className = "form-msg" + (text ? (isError ? " is-error" : " is-ok") : "");
}

/** 사진을 긴 쪽 1200px 이하 JPEG 로 줄임 */
async function shrink(file) {
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  const scale = Math.min(1, PHOTO_MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#fff";                         // 투명 PNG 는 흰 배경으로
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  if (bitmap.close) bitmap.close();
  return canvas.toDataURL("image/jpeg", 0.88);
}
