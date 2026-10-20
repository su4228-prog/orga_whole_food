// ============================================================
// sub.js — 상품 상세 페이지(sub.html) 전용 스크립트
// ── json/sub.json 을 불러와 화면을 렌더링하고 인터랙션을 연결한다
// ============================================================

import { loadProductDetail, detailUrl } from './api.js';

document.addEventListener('DOMContentLoaded', function () {
  // 주소의 ?id=번호 로 어떤 상품인지 정합니다. 서버가 없으면 json/sub.json(복숭아 병조림)을 보여줍니다.
  const id = new URLSearchParams(location.search).get('id');

  loadProductDetail(id, './json/sub.json')
    .then(function (data) {
      renderPage(data);
      bindInteractions(data);
      document.title = data.product.fullName + ' - ORGA Whole Foods';
    })
    .catch(function (err) {
      console.error('상품 데이터를 불러오지 못했습니다.', err);
      showError(err);
    });
});

function showError(err) {
  const notFound = err && (err.status === 404 || err.status === 422);
  const message = notFound ? '찾으시는 상품이 없습니다.' : '상품 정보를 불러오지 못했습니다.<br>잠시 후 다시 시도해 주세요.';
  document.querySelector('.product-detail-page .wrap').innerHTML =
    '<div class="detail-error"><p>' + message + '</p><a href="index.html">메인으로 돌아가기</a></div>';
}


// ============================================================
// 렌더링
// ============================================================

function renderPage(data) {
  document.getElementById('productGallery').innerHTML = renderGallery(data.product);
  document.getElementById('productInfo').innerHTML = renderProductInfo(data.product);
  document.getElementById('productBottomRow').innerHTML = renderBottomRow(data.product);
  document.getElementById('aiSliderTrack').innerHTML = data.aiRecommend.map(renderAiCard).join('');
  document.getElementById('productInfoTabList').innerHTML = renderInfoTabs(data.infoTabs);
  document.getElementById('productInfoContent').innerHTML = data.detailContent.map(renderDetailBlock).join('');
}

function renderGallery(product) {
  const badge = product.badge ? '<span class="best-badge">' + product.badge + '</span>' : '';

  const thumbnails = product.gallery.thumbnails.map(function (thumb, i) {
    return '' +
      '<button class="thumbnail-item' + (i === 0 ? ' active' : '') + '" data-image="' + thumb.image + '" type="button">' +
      '  <img alt="' + thumb.alt + '" src="' + thumb.image + '" />' +
      '</button>';
  }).join('');

  return '' +
    '<div class="main-image-box" id="mainImageBox">' +
    '  ' + badge +
    '  <img alt="' + product.gallery.mainAlt + '" id="mainProductImage" src="' + product.gallery.mainImage + '" />' +
    '  <div class="zoom-lens" id="zoomLens"></div>' +
    '  <button class="expand-image-button" type="button">⛶</button>' +
    '</div>' +
    '<div class="thumbnail-list">' + thumbnails + '</div>';
}

function renderProductInfo(product) {
  const infoRows = product.infoRows.map(function (row) {
    return '' +
      '<div class="product-info-row ' + row.rowClass + '">' +
      '  <div class="info-label">' + row.label + '</div>' +
      '  <div class="info-value">' + row.value + '</div>' +
      '</div>';
  }).join('');

  const deliveryTypes = product.delivery.types.map(function (t) {
    return '<span>' + t.icon + ' ' + t.label + '</span>';
  }).join('');

  const deliveryDetails = product.delivery.details.map(function (d) {
    const lines = d.lines.map(function (line) { return '<p>' + line + '</p>'; }).join('');
    return '' +
      '<div class="delivery-detail-row">' +
      '  <div class="delivery-icon">' + d.icon + '</div>' +
      '  <strong>' + d.title + '</strong>' +
      '  <div class="delivery-text">' + lines + '</div>' +
      '</div>';
  }).join('');

  return '' +
    '<div class="zoom-result" id="zoomResult"></div>' +
    '<div class="product-category">' + product.category + '</div>' +
    '<div class="product-brand-row">' +
    '  <div class="product-brand">' +
    '    <img alt="" src="' + product.brand.icon + '" />' +
    '    <strong>' + product.brand.name + '</strong>' +
    '  </div>' +
    '  <div class="product-action-icons">' +
    '    <button class="icon-button" id="heartButton" type="button"><img alt="찜하기" src="./img/icon/01_heart_icon.png" /></button>' +
    '    <button class="icon-button" id="shareButton" type="button"><img alt="공유하기" src="./img/icon/share_icon.png" /></button>' +
    '  </div>' +
    '</div>' +
    '<h1 class="product-name">' + product.nameLines.join('<br/>') + '</h1>' +
    (product.description ? '<p class="product-description">' + product.description + '</p>' : '<p class="product-description"></p>') +
    '<div class="product-price-area">' +
    // 할인 전 가격 · 할인율은 값이 있을 때만 보여줍니다
    (product.price.original != null ? '  <div class="original-price">' + product.price.original.toLocaleString() + '</div>' : '') +
    '  <div class="sale-price-row">' +
    '    <strong class="sale-price">' + product.price.sale.toLocaleString() + '<span>원</span></strong>' +
    (product.price.discountRate != null
      ? '    <strong class="discount-rate">' + product.price.discountRate + '%</strong>' +
        '    <button class="discount-info-button" type="button">할인정보<span>?</span></button>'
      : '') +
    '  </div>' +
    (product.price.unit ? '  <div class="unit-price">' + product.price.unit + '</div>' : '') +
    '</div>' +
    infoRows +
    '<div class="delivery-section closed">' +
    '  <button class="delivery-heading" id="deliveryToggle" type="button">' +
    '    <span class="delivery-title">배송정보</span>' +
    '    <div class="delivery-types">' + deliveryTypes + '</div>' +
    '    <span class="delivery-arrow">⌄</span>' +
    '  </button>' +
    '  <div class="delivery-detail">' + deliveryDetails + '</div>' +
    '</div>' +
    '<div class="order-box">' +
    '  <div class="order-product-name">' + product.fullName + '</div>' +
    '  <div class="order-bottom">' +
    '    <div class="quantity-control">' +
    '      <button id="minusButton" type="button">&minus;</button>' +
    '      <span id="quantity">1</span>' +
    '      <button id="plusButton" type="button">+</button>' +
    '    </div>' +
    '    <strong class="order-item-price" id="orderItemPrice">' + product.price.sale.toLocaleString() + '원</strong>' +
    '  </div>' +
    '</div>';
}

function renderBottomRow(product) {
  return '' +
    '<div class="product-bottom-left">' +
    '  <div class="product-review-summary">' +
    '    <strong>상품후기</strong>' +
    '    <div class="review-content">' +
    '      <div class="review-stars">★★★★★</div>' +
    '      <a href="#">' + product.reviewCount + '건 후기 더보기</a>' +
    '    </div>' +
    '  </div>' +
    '</div>' +
    '<div class="product-bottom-right">' +
    '  <div class="total-price-row">' +
    '    <span>주문금액</span>' +
    '    <strong id="totalPrice">' + product.price.sale.toLocaleString() + '<small>원</small></strong>' +
    '  </div>' +
    '  <div class="purchase-actions">' +
    '    <button class="purchase-button gift" id="giftButton" type="button"><img alt="" src="./img/icon/green_gift_icon.png" /><span>선물하기</span></button>' +
    '    <button class="purchase-button" id="cartButton" type="button">장바구니</button>' +
    '    <button class="purchase-button buy-now" id="buyNowButton" type="button">바로구매</button>' +
    '  </div>' +
    '</div>';
}

function renderAiCard(item) {
  const discount = item.discount ? '<span class="ai-discount">' + item.discount + '%</span>' : '';
  const unit = item.unit ? item.unit : '';
  const meta = (item.rating != null && item.reviewCount != null) ?
    '<img alt="" src="./img/icon/04_star_icon.png" /><span>' + item.rating + '</span>' +
    '<img alt="" src="./img/icon/03_chat_bubble_icon.png" /><span>' + item.reviewCount.toLocaleString() + '</span>' : '';
  const label = item.label ? '<span class="ai-label">' + item.label + '</span>' : '';
  const badge = item.badge ? '<span class="ai-best-badge">' + item.badge + '</span>' : '';

  return '' +
    '<article class="ai-card">' +
    // 상품 번호가 있는 연관 상품은 이미지를 누르면 그 상품의 상세로 이동합니다
    '  <div class="ai-product-image">' +
    (item.id != null
      ? '<a class="card-link" href="' + detailUrl(item) + '" target="_self"><img alt="' + item.alt + '" src="' + item.image + '" /></a>'
      : '<img alt="' + item.alt + '" src="' + item.image + '" />') +
    '</div>' +
    '  <div class="ai-card-actions">' +
    '    <img alt="찜" src="./img/icon/01_heart_icon.png" />' +
    '    <img alt="장바구니" src="./img/icon/02_add_cart.png" />' +
    '  </div>' +
    '  ' + badge +
    '  <div class="ai-brand">' + item.brand + '</div>' +
    '  <div class="ai-name">' + item.name + '</div>' +
    '  <div class="ai-price">' + discount + item.price.toLocaleString() + '원</div>' +
    '  <div class="ai-unit">' + unit + '</div>' +
    '  <div class="ai-meta">' + meta + '</div>' +
    '  ' + label +
    '</article>';
}

function renderInfoTabs(tabs) {
  return tabs.map(function (tab) {
    const count = tab.count != null ? '<span class="count">' + tab.count + '</span>' : '';
    return '' +
      '<a aria-disabled="true" class="product-info-tab' + (tab.active ? ' active' : '') + '" href="javascript:void(0)" role="button">' +
      tab.label + count +
      '</a>';
  }).join('');
}

function renderDetailBlock(block) {
  switch (block.type) {
    case 'image': {
      const variantClass = block.variant === 'logo' ? ' logo-block' : block.variant === 'narrow' ? ' narrow' : block.variant === 'product' ? ' product-shot' : '';
      return '<div class="product-detail-image-block' + variantClass + '"><img alt="' + block.alt + '" src="' + block.src + '" /></div>';
    }
    case 'storyIntro': {
      const points = block.points.map(function (p) {
        return '' +
          '<div class="product-story-point">' +
          '  <img alt="" src="' + p.icon + '" />' +
          '  <span>' + p.lines.join('<br/>') + '</span>' +
          '</div>';
      }).join('');
      return '' +
        '<div class="product-story">' +
        '  <div class="product-story-intro">' +
        '    <div class="product-story-kicker">' + block.kicker + '</div>' +
        '    <h2 class="product-story-title">' + block.title + '</h2>' +
        '    <p class="product-story-desc">' + block.desc + '</p>' +
        '    <div class="product-story-points">' + points + '</div>' +
        '  </div>' +
        '</div>';
    }
    case 'yellowPanel': {
      const boxes = block.boxes.map(function (b) {
        return '' +
          '<div class="product-compose-box">' +
          '  <strong>' + b.title + '</strong>' +
          '  ' + b.lines.join('<br/>') +
          '</div>';
      }).join('');
      return '' +
        '<div class="product-story">' +
        '  <div class="product-yellow-panel ' + (block.extraClass || '') + '">' +
        '    <h3>' + block.heading + '</h3>' +
        boxes +
        '  </div>' +
        '</div>';
    }
    case 'textSection': {
      const paragraphs = block.paragraphs.map(function (p) { return '<p>' + p + '</p>'; }).join('');
      const useful = block.usefulTitle ? '<div class="product-useful-title">' + block.usefulTitle + '</div>' : '';
      return '' +
        '<div class="product-story">' +
        '  <div class="product-text-section">' +
        '    <h3>' + block.heading + '</h3>' +
        paragraphs + useful +
        '  </div>' +
        '</div>';
    }
    case 'storage': {
      return '' +
        '<div class="product-story">' +
        '  <div class="product-storage">' +
        '    <strong>' + block.heading + '</strong>' +
        '    ' + block.text +
        '    <br/><br/>' +
        '    ' + block.note +
        '  </div>' +
        '</div>';
    }
    case 'brandMessage': {
      return '' +
        '<div class="product-story">' +
        '  <div class="product-brand-message">' +
        '    <img alt="' + block.alt + '" src="' + block.src + '" />' +
        '  </div>' +
        '</div>';
    }
    default:
      return '';
  }
}


// ============================================================
// 인터랙션 (렌더링 이후 DOM 기준으로 연결)
// ============================================================

function bindInteractions(data) {
  bindGalleryZoom();
  bindDeliveryToggle();
  bindQuantity(data.product.price.sale);
  bindHeartShare(data.product.fullName);
  bindPurchaseButtons();
  bindFloatingTop();
  bindAiSlider();
}

function bindGalleryZoom() {
  const mainImageBox = document.querySelector('#mainImageBox');
  const mainImage = document.querySelector('#mainProductImage');
  const zoomLens = document.querySelector('#zoomLens');
  const zoomResult = document.querySelector('#zoomResult');
  const thumbnails = document.querySelectorAll('.thumbnail-item');

  thumbnails.forEach(function (thumbnail) {
    thumbnail.addEventListener('click', function () {
      thumbnails.forEach(function (item) { item.classList.remove('active'); });
      thumbnail.classList.add('active');
      const imagePath = thumbnail.dataset.image;
      mainImage.src = imagePath;
      zoomResult.style.backgroundImage = "url('" + imagePath + "')";
    });
  });

  mainImageBox.addEventListener('mouseenter', function () {
    if (window.innerWidth <= 800) return;
    zoomLens.style.display = 'block';
    zoomResult.style.display = 'block';
    zoomResult.style.backgroundImage = "url('" + mainImage.src + "')";
  });

  mainImageBox.addEventListener('mouseleave', function () {
    zoomLens.style.display = 'none';
    zoomResult.style.display = 'none';
  });

  mainImageBox.addEventListener('mousemove', function (event) {
    if (window.innerWidth <= 800) return;
    const rect = mainImageBox.getBoundingClientRect();
    const lensWidth = zoomLens.offsetWidth;
    const lensHeight = zoomLens.offsetHeight;
    let x = event.clientX - rect.left - lensWidth / 2;
    let y = event.clientY - rect.top - lensHeight / 2;
    x = Math.max(0, Math.min(x, rect.width - lensWidth));
    y = Math.max(0, Math.min(y, rect.height - lensHeight));
    zoomLens.style.left = x + 'px';
    zoomLens.style.top = y + 'px';
    const zoomX = zoomResult.offsetWidth / lensWidth;
    const zoomY = zoomResult.offsetHeight / lensHeight;
    zoomResult.style.backgroundSize = rect.width * zoomX + 'px ' + rect.height * zoomY + 'px';
    zoomResult.style.backgroundPosition = '-' + x * zoomX + 'px -' + y * zoomY + 'px';
  });
}

function bindDeliveryToggle() {
  const deliveryToggle = document.querySelector('#deliveryToggle');
  const deliverySection = document.querySelector('.delivery-section');
  deliveryToggle.addEventListener('click', function () {
    deliverySection.classList.toggle('closed');
  });
}

function bindQuantity(productPrice) {
  const minusButton = document.querySelector('#minusButton');
  const plusButton = document.querySelector('#plusButton');
  const quantityText = document.querySelector('#quantity');
  const orderItemPrice = document.querySelector('#orderItemPrice');
  const totalPrice = document.querySelector('#totalPrice');

  let quantity = 1;

  function updatePrice() {
    const price = productPrice * quantity;
    quantityText.textContent = quantity;
    orderItemPrice.textContent = price.toLocaleString() + '원';
    totalPrice.innerHTML = price.toLocaleString() + '<small>원</small>';
  }

  plusButton.addEventListener('click', function () {
    quantity++;
    updatePrice();
  });

  minusButton.addEventListener('click', function () {
    if (quantity > 1) {
      quantity--;
      updatePrice();
    }
  });
}

function bindHeartShare(productName) {
  const heartButton = document.querySelector('#heartButton');
  const shareButton = document.querySelector('#shareButton');

  heartButton.addEventListener('click', function () {
    heartButton.classList.toggle('active');
  });

  shareButton.addEventListener('click', function () {
    if (navigator.share) {
      navigator.share({ title: productName, url: window.location.href });
    } else if (navigator.clipboard) {
      navigator.clipboard.writeText(window.location.href).then(function () {
        alert('상품 주소가 복사되었습니다.');
      });
    }
  });
}

function bindPurchaseButtons() {
  const giftButton = document.querySelector('#giftButton');
  const cartButton = document.querySelector('#cartButton');
  const buyNowButton = document.querySelector('#buyNowButton');

  if (giftButton) {
    giftButton.addEventListener('click', function () {
      alert('선물하기 버튼입니다.');
    });
  }

  if (cartButton) {
    cartButton.addEventListener('click', function () {
      alert('상품이 장바구니에 담겼습니다.');
    });
  }

  if (buyNowButton) {
    buyNowButton.addEventListener('click', function () {
      alert('바로구매 버튼입니다.');
    });
  }
}

function bindFloatingTop() {
  const floatingTop = document.querySelector('#floatingTop');
  floatingTop.addEventListener('click', function () {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
}

function bindAiSlider() {
  const track = document.getElementById('aiSliderTrack');
  const prevBtn = document.getElementById('aiPrevBtn');
  const nextBtn = document.getElementById('aiNextBtn');

  if (!track || !prevBtn || !nextBtn) return;

  const cards = Array.from(track.querySelectorAll('.ai-card'));
  let index = 0;

  function visibleCount() {
    if (window.innerWidth <= 650) return 2;
    if (window.innerWidth <= 1000) return 3;
    return 5;
  }

  function maxIndex() {
    return Math.max(0, cards.length - visibleCount());
  }

  function render() {
    if (!cards.length) return;

    index = Math.max(0, Math.min(index, maxIndex()));

    const cardWidth = cards[0].getBoundingClientRect().width;
    const gap = 20;
    const x = index * (cardWidth + gap);

    track.style.transform = 'translateX(-' + x + 'px)';

    prevBtn.disabled = index === 0;
    nextBtn.disabled = index === maxIndex();
  }

  nextBtn.addEventListener('click', function () {
    if (index < maxIndex()) {
      index += 1;
      render();
    }
  });

  prevBtn.addEventListener('click', function () {
    if (index > 0) {
      index -= 1;
      render();
    }
  });

  window.addEventListener('resize', render);
  render();
}
