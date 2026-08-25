// 추석 선물세트 사전예약
// json/gift_products.json

// export fetch(...) 형태로 직접 내보낼 수 없음
// fetch 코드를 함수로 감싼 후 그 함수를 export 해야 함

export function loadGiftProducts() {

  fetch("./json/gift_products.json")
    .then((res) => res.json())
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
              <a class="card-link" href="sub.html" target="_self"><img alt="${item.name}" src="${item.image}" /></a>
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
