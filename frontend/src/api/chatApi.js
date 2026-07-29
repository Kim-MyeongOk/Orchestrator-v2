import { AUTH_TOKEN_STORAGE_KEY }   from "../constants/storageKeys";
import { AUTH_USER_ID_STORAGE_KEY } from "../constants/storageKeys";
import { USER_ID_STORAGE_KEY }      from "../constants/storageKeys";
import { API_URL_STORAGE_KEY }      from "../constants/storageKeys";
import { LOGIN_PAGE_PATH }          from "../constants/storageKeys";
import { LOGOUT_REASON_STORAGE_KEY } from "../constants/storageKeys";
import { INPUT_DRAFT_STORAGE_KEY }   from "../constants/storageKeys";

// 서버가 토큰을 자동 연장할 때 실어 보내는 헤더 (백엔드 AuthTokenRenewalMiddleware 와 이름을 맞춘다)
const REFRESHED_AUTH_TOKEN_HEADER_NAME = "X-Refreshed-Auth-Token";

/* ══════════════════ 백엔드 베이스 URL ══════════════════
   우선순위 : 개발자 모드에서 저장한 값 > .env 의 VITE_API_URL > localhost:8000 */

const DEFAULT_API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

let apiBaseUrl = (localStorage.getItem(API_URL_STORAGE_KEY) || DEFAULT_API_URL).replace(/\/+$/, "");

export function getApiUrl() { return apiBaseUrl; }

export function setApiUrl(newApiUrl) {
    apiBaseUrl = (newApiUrl || "").trim().replace(/\/+$/, "");
    localStorage.setItem(API_URL_STORAGE_KEY, apiBaseUrl);
}

/* ══════════════════ 인증 ══════════════════ */

export function getAuthToken() { return localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) || ""; }

export function getUserId() { return localStorage.getItem(AUTH_USER_ID_STORAGE_KEY) || "anonymous"; }

export function logout(logoutReasonText = "") {
    // 인증 정보를 지우고 로그인 페이지로 이동한다 (방 목록은 서버에 남아 다음 로그인 시 복원).
    // 세션 만료처럼 사용자가 의도하지 않은 로그아웃이면 사유를 남겨, 다시 들어왔을 때 안내할 수 있게 한다.
    // 사유 없는 로그아웃 = 사용자가 직접 누른 것이므로 작성 중이던 초안도 함께 지운다
    // (세션 만료로 튕긴 경우에는 남겨 두었다가 다시 들어왔을 때 복원한다)
    if (logoutReasonText) localStorage.setItem(LOGOUT_REASON_STORAGE_KEY, logoutReasonText);
    else                  localStorage.removeItem(INPUT_DRAFT_STORAGE_KEY);
    localStorage.removeItem(AUTH_USER_ID_STORAGE_KEY);
    localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    localStorage.removeItem(USER_ID_STORAGE_KEY);
    location.replace(LOGIN_PAGE_PATH);
}

export function takeLogoutReasonText() {
    // 한 번 읽으면 지운다 (새로고침할 때마다 같은 안내가 다시 뜨지 않도록)
    const logoutReasonText = localStorage.getItem(LOGOUT_REASON_STORAGE_KEY) || "";
    if (logoutReasonText) localStorage.removeItem(LOGOUT_REASON_STORAGE_KEY);
    return logoutReasonText;
}

export class NonRetryableError extends Error {}   // 4xx 등 재시도가 무의미한 오류

function applyRefreshedAuthToken(response) {
    // Silent Refresh : 서버가 남은 수명이 절반 아래인 토큰을 보면 새 토큰을 헤더로 함께 내려준다.
    // 여기서 조용히 갈아끼우므로, 계속 쓰는 동안에는 만료로 튕기지 않는다.
    const refreshedToken = response.headers.get(REFRESHED_AUTH_TOKEN_HEADER_NAME);
    if (refreshedToken) localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, refreshedToken);
}

async function authFetch(pathText, init = {}) {
    // 인증 토큰을 Authorization 헤더로 실어 요청한다. 401(만료·무효) 이면 사유를 남기고 로그아웃한다.
    const headerDictionary = Object.assign({}, init.headers || {}, { "Authorization" : `Bearer ${getAuthToken()}` });
    const response         = await fetch(`${apiBaseUrl}${pathText}`, Object.assign({}, init, { headers : headerDictionary }));
    applyRefreshedAuthToken(response);
    if (response.status === 401) {
        logout("세션이 만료되어 다시 로그인했습니다. 작성 중이던 내용은 그대로 남아 있습니다.");
        throw new NonRetryableError("UNAUTHORIZED");
    }
    return response;
}

async function readJsonOrThrowAsync(response) {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}

/* ══════════════════ 채팅방 ══════════════════ */

export async function listRoomsAsync() {
    // 서버 응답(snake_case) → 화면 모델(camelCase) 로 변환한다. messages 는 lazy 로드 대상이므로 null.
    const result = await readJsonOrThrowAsync(await authFetch("/rooms"));
    return result.rooms.map(serverRoom => ({
        roomId          : serverRoom.room_id,
        threadId        : serverRoom.thread_id,
        title           : serverRoom.title,
        model           : serverRoom.model || "",
        reasoningEffort : serverRoom.reasoning_effort || "",
        messages        : null
    }));
}

export async function upsertRoomAsync(room) {
    // 방 메타(제목/모델/생각 정도/Thread)를 서버에 upsert — 실패해도 로컬 동작은 계속한다
    try {
        await authFetch("/rooms", {
            method  : "POST",
            headers : { "Content-Type" : "application/json" },
            body    : JSON.stringify({
                user_id          : getUserId(),
                room_id          : room.roomId,
                thread_id        : room.threadId,
                title            : room.title,
                model            : room.model || null,
                reasoning_effort : room.reasoningEffort || null
            })
        });
    } catch (_ignored) {}
}

export async function deleteRoomAsync(roomId) {
    try {
        await authFetch(`/rooms/${encodeURIComponent(roomId)}`, { method : "DELETE" });
    } catch (_ignored) {}
}

/* ══════════════════ 북마크 ══════════════════ */

export async function listBookmarksAsync() {
    // 서버 응답(snake_case) → 화면 모델(camelCase). 방 삭제 시 FK CASCADE 로 함께 지워지므로 유효한 것만 내려온다.
    const result = await readJsonOrThrowAsync(await authFetch("/bookmarks"));
    return result.bookmarks.map(serverBookmark => ({
        bookmarkId  : serverBookmark.bookmark_id,
        roomId      : serverBookmark.room_id,
        agentIndex  : serverBookmark.agent_index,
        text        : serverBookmark.text || "",
        memo        : serverBookmark.memo || "",
        completedAt : serverBookmark.completed_at || serverBookmark.created_at,
        createdAt   : serverBookmark.created_at
    }));
}

export async function upsertBookmarkAsync(bookmark) {
    // 낙관적 UI : 화면은 이미 갱신된 상태라 실패해도 되돌리지 않고 조용히 넘긴다 (다음 로드 때 서버 상태로 수렴)
    try {
        await authFetch("/bookmarks", {
            method  : "POST",
            headers : { "Content-Type" : "application/json" },
            body    : JSON.stringify({
                bookmark_id  : bookmark.bookmarkId,
                room_id      : bookmark.roomId,
                agent_index  : bookmark.agentIndex,
                text         : bookmark.text || "",
                completed_at : bookmark.completedAt || null,
                memo         : bookmark.memo || null
            })
        });
    } catch (_ignored) {}
}

export async function updateBookmarkMemoAsync(bookmarkId, memoText) {
    // 메모 수정은 사용자가 명시적으로 누른 동작이므로 조용히 삼키지 않고 던진다.
    // 호출 측(useBookmarks)에서 실패를 알리고 화면을 되돌린다.
    const response = await authFetch(`/bookmarks/${encodeURIComponent(bookmarkId)}`, {
        method  : "PATCH",
        headers : { "Content-Type" : "application/json" },
        body    : JSON.stringify({ memo : memoText || null })
    });
    const result = await readJsonOrThrowAsync(response);
    return result.memo || "";
}

export async function deleteBookmarkAsync(bookmarkId) {
    try {
        await authFetch(`/bookmarks/${encodeURIComponent(bookmarkId)}`, { method : "DELETE" });
    } catch (_ignored) {}
}

/* ══════════════════ 스레드(체크포인트) ══════════════════ */

export async function getThreadMessagesAsync(threadId) {
    const result = await readJsonOrThrowAsync(await authFetch(`/threads/${encodeURIComponent(threadId)}/messages`));
    return result.messages.map(serverMessage => ({
        role      : serverMessage.role,
        text      : serverMessage.text,
        reasoning : serverMessage.reasoning || ""
    }));
}

export async function truncateThreadAsync(threadId, keepHumanMessageCount) {
    // 질문 수정 시 : 이 질문 앞까지만 체크포인트에 남기고 이후를 제거한다
    const response = await authFetch(`/threads/${encodeURIComponent(threadId)}/truncate`, {
        method  : "POST",
        headers : { "Content-Type" : "application/json" },
        body    : JSON.stringify({ keep_human_message_count : keepHumanMessageCount })
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
}

/* ══════════════════ 모델 목록 ══════════════════ */

export async function listModelsAsync() {
    // 인증 없이 열려 있는 엔드포인트라 기본 fetch 를 쓴다
    const response = await fetch(`${apiBaseUrl}/models`);
    const result   = await readJsonOrThrowAsync(response);
    return { defaultModel : result.default_model, modelNameList : result.models };
}

/* ══════════════════ 스트리밍 (NDJSON) ══════════════════ */

export async function streamChatTurnAsync({ threadId, message, model, reasoningEffort, referencedText, referencedMessageIdList, imageUrlList, signal, onStart, onReasoning, onToken, onStreamError }) {
    // NDJSON 이벤트 스트림을 읽어 콜백으로 흘려보낸다.
    //   {"type":"start","run_id":...}     → onStart
    //   {"type":"reasoning","text":...}   → onReasoning (생각 과정)
    //   {"type":"token","text":...}       → onToken     (답변 본문)
    //   {"type":"error","text":...}       → onStreamError (200 스트림 본문으로 온 오류)
    const response = await authFetch("/stream", {
        method  : "POST",
        headers : { "Content-Type" : "application/json" },
        body    : JSON.stringify({
            thread_id         : threadId,
            message           : message,
            model             : model || null,
            reasoning_effort  : reasoningEffort || null,
            include_reasoning : true,
            referenced_text   : referencedText || null,   // 서버가 [참조 내용]/[질문] 형태로 조합한다
            referenced_message_id_list : referencedMessageIdList || [],  // 통째로 고른 이전 답변 ID ("agent-3")
            image_url_list             : imageUrlList || []              // MinIO 에 올린 이미지 URL (Vision 추론)
        }),
        signal : signal
    });

    if (!response.ok || !response.body) {
        // 서버가 준 에러 상세(본문)를 함께 담는다 (개발자 모드에서 실제 오류명과 함께 노출)
        let serverDetailText = "";
        try { serverDetailText = (await response.text()).trim().slice(0, 800); } catch (_ignored) {}
        const httpError = response.status >= 500
            ? new Error(`HTTP ${response.status} (서버 오류)`)
            : new NonRetryableError(`HTTP ${response.status}`);
        httpError.serverDetail = serverDetailText;
        throw httpError;   // 5xx → 재시도 대상(Error), 4xx → 즉시 실패(NonRetryableError)
    }

    // Run ID : include_reasoning=false 라 start 이벤트가 없는 경우를 위한 헤더 폴백
    const responseRunId = response.headers.get("X-Run-Id");
    if (responseRunId && onStart) onStart(responseRunId);

    const streamReader = response.body.getReader();
    const textDecoder  = new TextDecoder("utf-8");
    let   lineBuffer   = "";

    const dispatchEventLine = (eventLine) => {
        if (!eventLine.trim()) return;
        try {
            const streamEvent = JSON.parse(eventLine);
            if      (streamEvent.type === "start"     && onStart)       onStart(streamEvent.run_id);
            else if (streamEvent.type === "reasoning" && onReasoning)   onReasoning(streamEvent.text);
            else if (streamEvent.type === "token"     && onToken)       onToken(streamEvent.text);
            else if (streamEvent.type === "error"     && onStreamError) onStreamError(streamEvent.text);
        } catch (_ignored) {
            if (onToken) onToken(eventLine);   // NDJSON 이 아닌 구버전 서버 폴백
        }
    };

    while (true) {
        const { done, value } = await streamReader.read();
        if (done) break;
        lineBuffer += textDecoder.decode(value, { stream : true });
        const completeLineList = lineBuffer.split("\n");
        lineBuffer = completeLineList.pop();   // 마지막 조각은 미완성 라인일 수 있으므로 버퍼에 남긴다
        completeLineList.forEach(dispatchEventLine);
    }
    dispatchEventLine(lineBuffer);   // 종료 후 잔여 버퍼 처리
}

/* ══════════════════ 이미지 업로드 (MinIO) ══════════════════ */

export async function uploadImageAsync(imageFile) {
    // 이미지를 백엔드(/api/upload)로 보내 MinIO 에 저장하고 접근 URL 을 돌려받는다.
    // Content-Type 은 지정하지 않는다 — 브라우저가 multipart 경계값까지 넣어 직접 만들어야 한다.
    const formData = new FormData();
    formData.append("file", imageFile);

    const response = await authFetch("/api/upload", { method : "POST", body : formData });
    if (!response.ok) {
        // 서버가 준 한국어 안내(파일 형식·크기·스토리지 오류)를 그대로 보여준다
        let detailText = "";
        try { detailText = (await response.json()).detail; } catch (_ignored) {}
        throw new Error(detailText || `업로드 실패 (HTTP ${response.status})`);
    }
    const result = await response.json();
    return { objectKey : result.object_key, imageUrl : result.image_url, contentType : result.content_type, byteCount : result.byte_count };
}

