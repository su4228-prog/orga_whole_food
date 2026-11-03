// 03_fetch_gift.js — 추석 선물세트 사전예약 섹션 카드
// 데이터: /api/sections/gift — 서버가 없으면 json/gift_products.json (js/api.js)
// 함수로 내보내고 main.js 에서 실행합니다.

import { loadSection, detailUrl } from "./api.js";

export function loadGiftProducts() {

  loadSection("gift", "./json/gift_products.json")
    .then((data) => {

      const grid = document.querySelector(".gift-grid");

      grid.innerHTML = data.items.map((item) => {

        const badge = item.badge
          ? `<span class="gift-badge">${item.badge}</span>`
          : "";

        const discount = item.discount
          ? `<span class="discount">${item.discount}</span>`
          : "";

        const unit = item.unit_price
          ? `<div class="gift-unit">${item.unit_price}</div>`
          : "";

        const meta = (item.rating != null && item.reviews != null)
          ? `
            <div class="gift-meta">
              <img alt="" src="./img/icon/04_star_icon.png" />
              <span>${item.rating}</span>
              <img alt="" src="./img/icon/03_chat_bubble_icon.png" />
              <span>${item.reviews.toLocaleString()}</span>
            </div>
          `
          : "";

        return `
          <article class="gift-card">
            <div class="gift-image">
              <a class="card-link" href="${detailUrl(item)}" target="_self"><img alt="${item.name}" src="${item.image}" /></a>
            </div>
            <div class="gift-actions">
              <img alt="찜" src="./img/icon/01_heart_icon.png" />
              <img alt="장바구니 담기" src="./img/icon/02_add_cart.png" />
            </div>
            ${badge}
            <div class="gift-brand">${item.brand}</div>
            <div class="gift-name">${item.name}</div>
            <div class="gift-price">${discount}${item.price}</div>
            ${unit}
            ${meta}
          </article>
        `;

      }).join("");

    });
}
