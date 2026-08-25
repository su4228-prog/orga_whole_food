// main.js
// 각 기능별 JS 파일에서 export한 함수를 import하여
// 한 곳에서 실행하는 메인 JavaScript 파일

// 배너 슬라이더
import { initSlider } from "./slider.js";

// 고객 맞춤 추천 상품
import { loadClientProducts } from "./01_fetch_client.js";

// 올가 할인 특가
import { loadDiscountProducts } from "./02_fetch_discount.js";

// 추석 선물세트 사전예약
import { loadGiftProducts } from "./03_fetch_gift.js";

// MD 추천상품
import { loadMdProducts } from "./04_fetch_md.js";

// NEW 신상품
import { loadNewProducts } from "./05_fetch_new.js";

// 베스트 상품 추천
import { loadBestProducts } from "./06_fetch_best.js";


// ==============================
// 각 기능 실행
// ==============================

initSlider();

loadClientProducts();

loadDiscountProducts();

loadGiftProducts();

loadMdProducts();

loadNewProducts();

loadBestProducts();
