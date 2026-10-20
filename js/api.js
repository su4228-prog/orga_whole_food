// api.js — 상품 정보를 어디서 가져올지 정하는 공통 모듈
//
// 1) 서버(API)가 있으면 서버에서 가져오고
// 2) 서버가 없거나 응답이 없으면 기존 json/ 파일로 대신합니다.
//    → GitHub Pages 같은 정적 배포(서버 없음)에서도 사이트가 그대로 동작합니다.

// 서버를 인터넷(Render)에 올린 뒤 그 주소를 여기에 적습니다. 예: "https://orga-whole-food.onrender.com"
// 비어 있으면 GitHub Pages 같은 정적 배포에서는 json/ 파일을 씁니다.
const PROD_API_BASE = "";

const LOCAL_HOSTS = ["localhost", "127.0.0.1"];

/** 서버 주소를 돌려줍니다. 서버를 쓰지 않으면 null */
export function apiBase() {
  if (LOCAL_HOSTS.includes(location.hostname)) {
    // 서버(8000번)가 사이트도 함께 보여주는 중이면 같은 주소, 다른 포트로 열었으면 로컬 서버 주소
    return location.port === "8000" ? "" : "http://127.0.0.1:8000";
  }
  // Render 서버가 사이트도 함께 보여주는 중이면 같은 주소
  if (location.hostname.endsWith(".onrender.com") || location.origin === PROD_API_BASE) return "";
  return PROD_API_BASE || null;
}

async function getJson(url, timeoutMs = 4000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: ctrl.signal });
    if (!res.ok) {
      const err = new Error(`${res.status} ${url}`);
      err.status = res.status;
      throw err;
    }
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

/** 섹션(client · discount · gift · md · new · best)의 상품 목록 */
export async function loadSection(key, fallbackJson) {
  const base = apiBase();
  if (base !== null) {
    try {
      return await getJson(`${base}/api/sections/${key}`);
    } catch (e) {
      console.warn(`[api] 서버에서 '${key}' 를 가져오지 못해 json 파일로 대신합니다.`, e.message);
    }
  }
  return getJson(fallbackJson);
}

/** 상품 상세. 없는 상품(404)이나 잘못된 번호(422)는 json 으로 대신하지 않고 오류로 알립니다. */
export async function loadProductDetail(id, fallbackJson) {
  const base = apiBase();
  if (base !== null && id) {
    try {
      return await getJson(`${base}/api/products/${encodeURIComponent(id)}`);
    } catch (e) {
      if (e.status === 404 || e.status === 422) throw e;
      console.warn("[api] 서버에서 상세를 가져오지 못해 json 파일로 대신합니다.", e.message);
    }
  }
  return getJson(fallbackJson);
}

/** 카드 → 상세 페이지 주소. 상품 번호가 있으면 ?id= 를 붙입니다. */
export function detailUrl(item) {
  return item && item.id != null ? `sub.html?id=${encodeURIComponent(item.id)}` : "sub.html";
}
