/** @type {import('tailwindcss').Config} */
// 기존 chat.html 은 Tailwind Play CDN(v3) + darkMode:"class" 로 동작했다.
// 동일한 클래스가 그대로 살아나도록 v3 설정을 유지한다 (v4 는 shadow-* 스케일 등이 달라 외형이 바뀐다).
export default {
    darkMode : "class",
    content  : ["./index.html", "./src/**/*.{js,jsx}"],
    // 키프레임/애니메이션은 src/index.css 에 원본 CSS 그대로 두었다 (.bubble-enter / .toast-enter / .typing-dot)
    theme    : { extend : {} },
    plugins  : []
};
