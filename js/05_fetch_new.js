// NEW 신상품
// json/new_products.json

// export fetch(...) 형태로 직접 내보낼 수 없음
// fetch 코드를 함수로 감싼 후 그 함수를 export 해야 함

// 서버(API)가 있으면 서버에서, 없으면 json 파일에서 가져옵니다 (js/api.js)
import { loadSection, detailUrl } from "./api.js";

export function loadNewProducts() {

  loadSection("new", "./json/new_products.json")
    .then((data) => {

      const grid = document.querySelector(".new-grid");

      grid.innerHTML = data.items.map((item) => {

        return `
          <article class="new-card">
            <div class="new-main-image">
              <a class="card-link" href="${detailUrl(item)}" target="_self"><img alt="${item.name} 메인 이미지" src="${item.main_image}" /></a>
            </div>
            <div class="new-bottom">
              <div class="new-thumb">
                <a class="card-link" href="${detailUrl(item)}" target="_self"><img alt="${item.name} 상품 이미지" src="${item.thumb}" /></a>
              </div>
              <div class="new-info">
                <div class="new-brand">${item.brand}</div>
                <div class="new-name">${item.name}</div>
                <div class="new-price">${item.price}</div>
                <div class="new-meta">
                  <img alt="" src="./img/icon/04_star_icon.png" />
                  <span>${item.rating}</span>
                  <img alt="" src="./img/icon/03_chat_bubble_icon.png" />
                  <span>${item.reviews}</span>
                </div>
              </div>
            </div>
          </article>
        `;

      }).join("");

    });
}
