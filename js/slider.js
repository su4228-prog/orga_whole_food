// slider.js — 메인 배너 슬라이더 (#sliderTrack)
// 3장씩(모바일 1장) 보여주고 3.5초마다 넘김 · 이전/다음 · 일시정지 · 현재 번호
// 함수로 내보내고 main.js 에서 실행합니다.

export function initSlider() {

  const track = document.getElementById("sliderTrack");
  const slides = Array.from(track.querySelectorAll(".slide"));
  const prevBtn = document.getElementById("prevBtn");
  const nextBtn = document.getElementById("nextBtn");
  const pauseBtn = document.getElementById("pauseBtn");
  const currentNum = document.getElementById("currentNum");

  let currentSlide = 0;
  let playing = true;
  let timer = null;

  function visibleCount(){
    return window.innerWidth <= 760 ? 1 : 3;
  }

  function maxVisualIndex(){
    return Math.max(0, slides.length - visibleCount());
  }

  function gapSize(){
    return 18;
  }

  function render(){
    var visualIndex = Math.min(currentSlide, maxVisualIndex());
    visualIndex = Math.max(0, visualIndex);

    const slideWidth = slides[0].getBoundingClientRect().width;
    const x = visualIndex * (slideWidth + gapSize());
    track.style.transform = `translateX(-${x}px)`;

    currentNum.textContent = currentSlide + 1;
  }

  function next(){
    currentSlide++;
    if(currentSlide >= slides.length) currentSlide = 0;
    render();
  }

  function prev(){
    currentSlide--;
    if(currentSlide < 0) currentSlide = slides.length - 1;
    render();
  }

  function startAuto(){
    clearInterval(timer);
    if(playing){
      timer = setInterval(next, 3500);
    }
  }

  prevBtn.addEventListener("click", () => {
    prev();
    startAuto();
  });

  nextBtn.addEventListener("click", () => {
    next();
    startAuto();
  });

  pauseBtn.addEventListener("click", () => {
    playing = !playing;
    pauseBtn.textContent = playing ? "Ⅱ" : "▶";
    pauseBtn.setAttribute("aria-label", playing ? "자동재생 정지" : "자동재생 시작");
    startAuto();
  });

  window.addEventListener("resize", render);

  render();
  startAuto();
}
