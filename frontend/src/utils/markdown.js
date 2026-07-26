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

export function stripMarkdownForSpeech(rawText) {
    // 음성 낭독용 : 마크다운 기호를 걷어낸 평문.
    // 원문을 그대로 넘기면 "별표 별표 굵게 별표 별표" 처럼 기호까지 읽고, 코드블록은 낭독할 의미가 없다.
    return (rawText || "")
        .replace(/```[\s\S]*?```/g, " (코드 블록 생략) ")   // 코드블록 : 낭독 대신 생략을 알린다
        .replace(/`([^`]+)`/g, "$1")                        // 인라인 코드
        .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")              // 이미지
        .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")            // 링크 : URL 은 버리고 표시 텍스트만
        .replace(/^\s{0,3}#{1,6}\s+/gm, "")                 // 제목
        .replace(/^\s{0,3}>\s?/gm, "")                      // 인용
        .replace(/^\s*[-*+]\s+/gm, "")                      // 목록 기호
        .replace(/^\s*\|.*\|\s*$/gm, " ")                   // 표 : 구분자가 소음이라 통째로 뺀다
        .replace(/\*\*([^*]+)\*\*/g, "$1")                  // 굵게
        .replace(/\*([^*]+)\*/g, "$1")                      // 기울임
        .replace(/~~([^~]+)~~/g, "$1")                      // 취소선
        .replace(/\n{2,}/g, "\n")
        .trim();
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
