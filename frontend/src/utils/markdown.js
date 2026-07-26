// npm i marked dompurify — 기존 chat.html 은 CDN 으로 로드했으나 번들 의존성으로 바꿨다.
import { marked }  from "marked";
import DOMPurify   from "dompurify";

export function renderMarkdownToHtml(rawText) {
    // 답변 원문(마크다운) → XSS 제거된 안전한 HTML. LLM 이 만든 <script> / onerror 등을 DOMPurify 가 걷어낸다.
    const parsedHtml = marked.parse(rawText || "", { breaks : true, gfm : true });
    return DOMPurify.sanitize(parsedHtml);
}

export function stripMarkdownForPreview(rawText, maximumLength = 90) {
    // 북마크 목록 미리보기용 : 마크다운 기호를 걷어낸 한 줄 요약
    return (rawText || "").replace(/[#*`>_~-]/g, " ").replace(/\s+/g, " ").trim().slice(0, maximumLength);
}

export async function writeTextToClipboard(copyText) {
    // 클립보드 쓰기 (HTTPS/권한 문제로 클립보드 API 를 못 쓰는 환경은 임시 textarea 폴백)
    try {
        await navigator.clipboard.writeText(copyText);
    } catch (_ignored) {
        const fallbackTextarea = document.createElement("textarea");
        fallbackTextarea.value = copyText;
        document.body.appendChild(fallbackTextarea);
        fallbackTextarea.select();
        document.execCommand("copy");
        fallbackTextarea.remove();
    }
}
