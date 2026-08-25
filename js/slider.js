// 배너 슬라이더
// index.html의 #sliderTrack 캐러셀을 동작시키는 기능

// export fetch(...) 형태처럼 즉시 실행 코드는 바로 export 할 수 없음
// 이 슬라이더는 fetch는 아니지만 같은 이유로 함수로 감싼 후 export 함
// (감싸지 않으면 import 되는 순간 바로 실행되어 실행 시점을 제어할 수 없음)

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
