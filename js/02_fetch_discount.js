// 올가 할인 특가
// json/discount_products.json

// export fetch(...) 형태로 직접 내보낼 수 없음
// fetch 코드를 함수로 감싼 후 그 함수를 export 해야 함

export function loadDiscountProducts() {

  fetch("./json/discount_products.json")
    .then((res) => res.json())
    .then((data) => {

      const grid = document.querySelector(".discount-grid");

      grid.innerHTML = data.items.map((item) => {

        const badge = item.badge
          ? `<span class="discount-badge">${item.badge}</span>`
          : "";

        const discount = item.discount
          ? `<span class="discount-rate">${item.discount}</span>`
          : "";

        const unit = item.unit_price
          ? `<div class="discount-unit">${item.unit_price}</div>`
          : "";

        const meta = (item.rating != null && item.reviews != null)
          ? `
            <div class="discount-meta">
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

        return `
          <article class="discount-card">
            <div class="discount-image">
              <a class="card-link" href="sub.html" target="_self"><img alt="${item.name}" src="${item.image}" /></a>
            </div>
            <div class="discount-actions">
              <img alt="찜" src="./img/icon/01_heart_icon.png" />
              <img alt="장바구니 담기" src="./img/icon/02_add_cart.png" />
            </div>
            ${badge}
            <div class="discount-brand">${item.brand}</div>
            <div class="discount-name">${item.name}</div>
            <div class="discount-price">${discount}${item.price}</div>
            ${unit}
            ${meta}
            ${delivery}
          </article>
        `;

      }).join("");

    });
}
