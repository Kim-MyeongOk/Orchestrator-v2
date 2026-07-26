import { AUTH_TOKEN_STORAGE_KEY }   from "../constants/storageKeys";
import { AUTH_USER_ID_STORAGE_KEY } from "../constants/storageKeys";
import { USER_ID_STORAGE_KEY }      from "../constants/storageKeys";
import { API_URL_STORAGE_KEY }      from "../constants/storageKeys";
import { LOGIN_PAGE_PATH }          from "../constants/storageKeys";

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

export function logout() {
    // 인증 정보를 지우고 로그인 페이지로 이동한다 (방 목록은 서버에 남아 다음 로그인 시 복원)
    localStorage.removeItem(AUTH_USER_ID_STORAGE_KEY);
    localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    localStorage.removeItem(USER_ID_STORAGE_KEY);
    location.replace(LOGIN_PAGE_PATH);
}

export class NonRetryableError extends Error {}   // 4xx 등 재시도가 무의미한 오류

async function authFetch(pathText, init = {}) {
    // 인증 토큰을 Authorization 헤더로 실어 요청한다. 401(만료·무효) 이면 로그아웃 처리.
    const headerDictionary = Object.assign({}, init.headers || {}, { "Authorization" : `Bearer ${getAuthToken()}` });
    const response         = await fetch(`${apiBaseUrl}${pathText}`, Object.assign({}, init, { headers : headerDictionary }));
    if (response.status === 401) {
        logout();
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

export async function streamChatTurnAsync({ threadId, message, model, reasoningEffort, signal, onStart, onReasoning, onToken, onStreamError }) {
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
            include_reasoning : true
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
