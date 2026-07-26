// 기존 chat.html 과 동일한 localStorage 키를 쓴다 — 기존 사용자의 방/북마크/설정이 그대로 승계된다.

export const THEME_STORAGE_KEY          = "orchestrator_chat_theme";
export const ROOM_STORAGE_KEY           = "orchestrator_chat_rooms_v1";
export const BOOKMARK_STORAGE_KEY       = "orchestrator_chat_bookmarks_v1";
export const USER_ID_STORAGE_KEY        = "orchestrator_chat_user_id";
export const AUTH_USER_ID_STORAGE_KEY   = "orchestrator_chat_auth_user_id";   // 로그인 인증된 사용자 ID (legacy/login.html 이 저장)
export const AUTH_TOKEN_STORAGE_KEY     = "orchestrator_chat_auth_token";     // 인증 토큰 (Authorization: Bearer 로 전송)
export const DEVELOPER_MODE_STORAGE_KEY = "orchestrator_chat_developer_mode";
export const API_URL_STORAGE_KEY        = "orchestrator_chat_api_url";
export const LOGOUT_REASON_STORAGE_KEY  = "orchestrator_chat_logout_reason";   // 세션 만료 등 의도치 않은 로그아웃 사유 (재접속 시 1회 안내)
export const INPUT_DRAFT_STORAGE_KEY    = "orchestrator_chat_input_draft";     // 작성 중이던 입력 (튕겨도 잃지 않도록 보관)

// 로그인 페이지 경로 : 기존 HTML 을 public/legacy 로 옮겼으므로 /legacy/login.html 로 서빙된다
export const LOGIN_PAGE_PATH = "/legacy/login.html";

export function readJsonFromStorage(storageKey, fallbackValue) {
    // JSON 파싱 실패(수동 편집·구버전 포맷)는 조용히 기본값으로 되돌린다
    try {
        const parsedValue = JSON.parse(localStorage.getItem(storageKey));
        return parsedValue === null || parsedValue === undefined ? fallbackValue : parsedValue;
    } catch (_ignored) {
        return fallbackValue;
    }
}

export function writeJsonToStorage(storageKey, value) {
    try {
        localStorage.setItem(storageKey, JSON.stringify(value));
    } catch (_ignored) {}
}
