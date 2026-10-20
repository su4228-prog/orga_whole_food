// MD 추천상품
// json/md_products.json

// export fetch(...) 형태로 직접 내보낼 수 없음
// fetch 코드를 함수로 감싼 후 그 함수를 export 해야 함

// 서버(API)가 있으면 서버에서, 없으면 json 파일에서 가져옵니다 (js/api.js)
import { loadSection, detailUrl } from "./api.js";

export function loadMdProducts() {

  loadSection("md", "./json/md_products.json")
    .then((data) => {

      const grid = document.querySelector(".md-grid");

      grid.innerHTML = data.items.map((item) => {

        const badge = item.badge
          ? `<span class="md-badge">${item.badge}</span>`
          : "";

        const discount = item.discount
          ? `<span class="discount">${item.discount}</span>`
          : "";

        const unit = item.unit_price
          ? `<div class="md-unit">${item.unit_price}</div>`
          : "";

        const meta = (item.rating != null && item.reviews != null)
          ? `
            <div class="md-meta">
              <img alt="" src="./img/icon/04_star_icon.png" />
              <span>${item.rating}</span>
              <img alt="" src="./img/icon/03_chat_bubble_icon.png" />
              <span>${item.reviews.toLocaleString()}</span>
            </div>
          `
          : "";

        return `
          <article class="md-card">
            <div class="md-image">
              <a class="card-link" href="${detailUrl(item)}" target="_self"><img alt="${item.name}" src="${item.image}" /></a>
            </div>
            <div class="md-actions">
              <img alt="찜" src="./img/icon/01_heart_icon.png" />
              <img alt="장바구니 담기" src="./img/icon/02_add_cart.png" />
            </div>
            ${badge}
            <div class="md-brand">${item.brand}</div>
            <div class="md-name">${item.name}</div>
            <div class="md-price">${discount}${item.price}</div>
            ${unit}
            ${meta}
          </article>
        `;

      }).join("");

    });
}
