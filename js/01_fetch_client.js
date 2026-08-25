// 고객 맞춤 추천 상품 (#AI 추천)
// json/client_products.json

// export fetch(...) 형태로 직접 내보낼 수 없음
// fetch 코드를 함수로 감싼 후 그 함수를 export 해야 함

export function loadClientProducts() {

  fetch("./json/client_products.json")
    .then((res) => res.json())
    .then((data) => {

      const grid = document.querySelector(".client-product-grid");

      grid.innerHTML = data.items.map((item) => {

        const badge = item.badge
          ? `<span class="client-badge">${item.badge}</span>`
          : "";

        const discount = item.discount
          ? `<span class="discount">${item.discount}</span>`
          : "";

        const unit = item.unit_price
          ? `<div class="client-unit">${item.unit_price}</div>`
          : "";

        const meta = (item.rating != null && item.reviews != null)
          ? `
            <div class="client-meta">
              <img alt="" src="./img/icon/04_star_icon.png" />
              <span>${item.rating}</span>
              <img alt="" src="./img/icon/03_chat_bubble_icon.png" />
              <span>${item.reviews.toLocaleString()}</span>
            </div>
          `
          : "";

        const delivery = item.delivery_badge
          ? `<span class="delivery-label">${item.delivery_badge}</span>`
          : "";

        const extra = item.extra_badge
          ? `<span class="best-label">${item.extra_badge}</span>`
          : "";

        return `
          <article class="client-card">
            <div class="client-image">
              <a class="card-link" href="sub.html" target="_self"><img alt="${item.name}" src="${item.image}" /></a>
            </div>
            <div class="client-actions">
              <img alt="찜" src="./img/icon/01_heart_icon.png" />
              <img alt="장바구니 담기" src="./img/icon/02_add_cart.png" />
            </div>
            ${badge}
            <div class="client-brand">${item.brand}</div>
            <div class="client-name">${item.name}</div>
            <div class="client-price">${discount}${item.price}</div>
            ${unit}
            ${meta}
            ${delivery}
            ${extra}
          </article>
        `;

      }).join("");

    });
}
