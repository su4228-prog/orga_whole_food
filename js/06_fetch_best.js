// 베스트 상품 추천 (랭킹 1~10위, 그리드 2개로 분리)
// json/best_products.json

// export fetch(...) 형태로 직접 내보낼 수 없음
// fetch 코드를 함수로 감싼 후 그 함수를 export 해야 함

export function loadBestProducts() {

  fetch("./json/best_products.json")
    .then((res) => res.json())
    .then((data) => {

      const firstGrid = document.querySelector(".best-grid");
      const secondGrid = document.querySelector(".best-grid-second");

      function renderCard(item) {

        const rank = String(item.rank).padStart(2, "0");

        const discount = item.discount
          ? `<span class="discount">${item.discount}</span>`
          : "";

        const unit = item.unit_price
          ? `<div class="best-unit">${item.unit_price}</div>`
          : "";

        const meta = (item.rating != null && item.reviews != null)
          ? `
            <div class="best-meta">
              <img alt="" src="./img/icon/04_star_icon.png" />
              <span>${item.rating}</span>
              <img alt="" src="./img/icon/03_chat_bubble_icon.png" />
              <span>${item.reviews.toLocaleString()}</span>
            </div>
          `
          : "";

        const label = item.extra_badge
          ? `<span class="best-label">${item.extra_badge}</span>`
          : item.delivery_badge
            ? `<span class="best-label">${item.delivery_badge}</span>`
            : "";

        return `
          <article class="best-card">
            <div class="best-rank">${rank}_</div>
            <div class="best-image">
              <a class="card-link" href="sub.html" target="_self"><img alt="${item.name}" src="${item.image}" /></a>
            </div>
            <div class="best-actions">
              <img alt="찜" src="./img/icon/01_heart_icon.png" />
              <img alt="장바구니 담기" src="./img/icon/02_add_cart.png" />
            </div>
            <div class="best-brand">${item.brand}</div>
            <div class="best-name">${item.name}</div>
            <div class="best-price">${discount}${item.price}</div>
            ${unit}
            ${meta}
            ${label}
          </article>
        `;
      }

      firstGrid.innerHTML = data.items.slice(0, 5).map(renderCard).join("");
      secondGrid.innerHTML = data.items.slice(5, 10).map(renderCard).join("");

    });
}
