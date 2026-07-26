import { useCallback } from "react";
import { useRef }      from "react";
import { useState }    from "react";

import { NonRetryableError }    from "../api/chatApi";
import { streamChatTurnAsync }  from "../api/chatApi";

const STREAM_MAXIMUM_RETRY_COUNT = 3;      // 최대 자동 재시도 횟수
const STREAM_BASE_DELAY_MS       = 1000;   // 지수 백오프 기본 간격 : 1초 → 2초 → 4초

function sleepAsync(delayMs) { return new Promise(resolve => setTimeout(resolve, delayMs)); }

function createEmptyStreamBuffer() {
    return { text : "", reasoning : "", reasoningTokenCount : 0, answerTokenCount : 0 };
}

/* 스트리밍 1턴 실행 : 5xx/네트워크 오류 시 지수 백오프로 자동 재시도하고,
   최종 실패 시 토스트 + (메시지에 붙는) 수동 재시도 버튼을 제공한다.

   토큰마다 setState 하면 렌더가 과해지므로 ref 에 누적하고 requestAnimationFrame 으로 한 번씩 흘려보낸다. */

export function useChatStream({ appendMessage, applyFirstMessageTitle, setRoomLastRunId, showToast, isDeveloperMode }) {
    const [isStreaming, setIsStreaming]       = useState(false);
    const [streamingState, setStreamingState] = useState(null);   // { text, reasoning, reasoningTokenCount, answerTokenCount, startedAt, retryNoticeText }

    const streamBufferRef   = useRef(createEmptyStreamBuffer());
    const flushFrameIdRef   = useRef(null);
    const abortControllerRef = useRef(null);

    const cancelPendingFlush = useCallback(() => {
        if (flushFrameIdRef.current === null) return;
        cancelAnimationFrame(flushFrameIdRef.current);
        flushFrameIdRef.current = null;
    }, []);

    const scheduleStreamFlush = useCallback(() => {
        if (flushFrameIdRef.current !== null) return;
        flushFrameIdRef.current = requestAnimationFrame(() => {
            flushFrameIdRef.current = null;
            setStreamingState(previousState => (previousState ? { ...previousState, ...streamBufferRef.current } : previousState));
        });
    }, []);

    const stopStreaming = useCallback(() => {
        if (abortControllerRef.current) abortControllerRef.current.abort();
    }, []);

    const executeStreamTurnAsync = useCallback(async (room, messageText, referencedText = "") => {
        const formatElapsedSecondText = (startedAt) => ((performance.now() - startedAt) / 1000).toFixed(1);

        streamBufferRef.current = createEmptyStreamBuffer();
        const turnStartedAt     = performance.now();
        abortControllerRef.current = new AbortController();

        setIsStreaming(true);
        setStreamingState({ ...streamBufferRef.current, startedAt : turnStartedAt, retryNoticeText : "" });

        const hasReceivedAnyText = () => streamBufferRef.current.text !== "" || streamBufferRef.current.reasoning !== "";
        const buildAgentMessage  = () => ({
            role      : "agent",
            text      : streamBufferRef.current.text.replace(/\s+$/, ""),   // 후행 공백 제거 (저장은 마크다운 원문)
            reasoning : streamBufferRef.current.reasoning,
            meta      : {
                elapsed_second_text   : formatElapsedSecondText(turnStartedAt),
                reasoning_token_count : streamBufferRef.current.reasoningTokenCount,
                answer_token_count    : streamBufferRef.current.answerTokenCount,
                completed_at          : Date.now()
            }
        });

        let attemptCount   = 0;
        let finalStatus    = { text : "대기", toneClass : "bg-slate-400 dark:bg-slate-600" };

        while (true) {
            let streamErrorText = null;   // 서버가 200 스트림 본문으로 보고한 오류(예: 429 quota)
            try {
                await streamChatTurnAsync({
                    threadId        : room.threadId,
                    message         : messageText,
                    model           : room.model,
                    reasoningEffort : room.reasoningEffort,
                    referencedText  : referencedText,
                    signal          : abortControllerRef.current.signal,
                    onStart         : (runId) => { if (runId) setRoomLastRunId(room.roomId, runId); },
                    onReasoning     : (chunkText) => {
                        streamBufferRef.current.reasoning           += chunkText;
                        streamBufferRef.current.reasoningTokenCount += 1;
                        setStreamingState(previousState => (previousState && previousState.retryNoticeText ? { ...previousState, retryNoticeText : "" } : previousState));
                        scheduleStreamFlush();
                    },
                    onToken : (chunkText) => {
                        // 선두 개행/공백 제거 : 첫 토큰에서만 (말풍선이 빈 줄로 부풀지 않게)
                        const appendedText = streamBufferRef.current.text === "" ? chunkText.replace(/^\s+/, "") : chunkText;
                        if (appendedText === "") return;
                        streamBufferRef.current.text             += appendedText;
                        streamBufferRef.current.answerTokenCount += 1;
                        setStreamingState(previousState => (previousState && previousState.retryNoticeText ? { ...previousState, retryNoticeText : "" } : previousState));
                        scheduleStreamFlush();
                    },
                    onStreamError : (errorText) => { streamErrorText = errorText; }
                });

                if (streamErrorText !== null) {
                    // 서버가 스트림 도중 오류를 보고 : 성공 저장 대신 오류로 처리한다 (개발자 모드는 원문 노출)
                    const shownErrorText = isDeveloperMode
                        ? `응답 오류 : ${streamErrorText}`
                        : "응답 오류 : 서버가 응답을 생성하지 못했습니다. 잠시 후 다시 시도해주세요.";
                    if (hasReceivedAnyText()) {
                        // 일부 답변을 이미 받았으면 그 부분은 보존하고 오류는 별도 안내로 남긴다
                        appendMessage(room.roomId, buildAgentMessage());
                        appendMessage(room.roomId, { role : "error", text : shownErrorText });
                    } else {
                        appendMessage(room.roomId, { role : "error", text : shownErrorText, retryMessageText : messageText, retryReferencedText : referencedText });
                    }
                    finalStatus = { text : "오류", toneClass : "bg-red-500" };
                    showToast(`⚠ ${isDeveloperMode ? streamErrorText : "서버 응답 오류 — 잠시 후 다시 시도해주세요."}`);
                    break;
                }

                appendMessage(room.roomId, buildAgentMessage());
                break;
            } catch (error) {
                // 사용자가 중단(Stop) : 재시도·에러 표시 없이 지금까지 받은 내용을 확정하고 조용히 종료한다
                if (error.name === "AbortError") {
                    if (hasReceivedAnyText()) appendMessage(room.roomId, buildAgentMessage());
                    else                      appendMessage(room.roomId, { role : "error", text : "응답을 중단했습니다." });
                    finalStatus = { text : "중단됨", toneClass : "bg-slate-400 dark:bg-slate-600" };
                    break;
                }

                // 자동 재시도 조건 : 재시도 가능 오류 + 아직 아무 데이터도 못 받음(중복 응답 방지) + 횟수 남음
                const isRetryable = !(error instanceof NonRetryableError) && !hasReceivedAnyText() && attemptCount < STREAM_MAXIMUM_RETRY_COUNT;
                if (isRetryable) {
                    attemptCount += 1;
                    const backoffDelayMs = STREAM_BASE_DELAY_MS * 2 ** (attemptCount - 1);   // 1초 → 2초 → 4초
                    setStreamingState(previousState => (previousState
                        ? { ...previousState, retryNoticeText : `연결 실패 — ${backoffDelayMs / 1000}초 후 자동 재시도 (${attemptCount}/${STREAM_MAXIMUM_RETRY_COUNT})` }
                        : previousState));
                    await sleepAsync(backoffDelayMs);
                    continue;
                }

                // 최종 실패 : 에러 메시지 + 토스트 + 수동 재시도 버튼
                const failReasonText = hasReceivedAnyText() ? "응답 중 연결이 끊겼습니다" : `응답 실패 : ${error.message}`;
                let   shownErrorText;
                if (isDeveloperMode) {
                    // 개발자 모드 : 일반 안내 대신 실제 오류명·메시지·서버 응답 상세를 그대로 노출한다
                    const detailLineList = [failReasonText, `[${error.name || "Error"}] ${error.message}`];
                    if (error.serverDetail) detailLineList.push(`서버 응답 : ${error.serverDetail}`);
                    detailLineList.push(`(자동 재시도 ${attemptCount}회 시도)`);
                    shownErrorText = detailLineList.join("\n");
                } else {
                    shownErrorText = `${failReasonText} — 자동 재시도 ${attemptCount}회 모두 실패했거나 재시도할 수 없는 오류입니다.`;
                }
                if (hasReceivedAnyText()) appendMessage(room.roomId, buildAgentMessage());
                appendMessage(room.roomId, { role : "error", text : shownErrorText, retryMessageText : messageText, retryReferencedText : referencedText });
                finalStatus = { text : "오류", toneClass : "bg-red-500" };
                showToast(`⚠ ${failReasonText}\n백엔드(포트 8000) 실행 여부를 확인한 뒤 '다시 시도'를 눌러주세요.`);
                break;
            }
        }

        cancelPendingFlush();
        abortControllerRef.current = null;
        streamBufferRef.current    = createEmptyStreamBuffer();
        setStreamingState(null);
        setIsStreaming(false);
        return finalStatus;
    }, [appendMessage, cancelPendingFlush, isDeveloperMode, scheduleStreamFlush, setRoomLastRunId, showToast]);

    const sendMessageAsync = useCallback(async (room, messageText, referencedText = "") => {
        // 사용자 메시지를 먼저 확정 저장한 뒤 스트리밍을 시작한다 (첫 메시지는 방 제목이 된다)
        // referencedText 는 말풍선에 인용 블록으로 보여주기 위해 함께 저장한다 (제목에는 쓰지 않는다)
        appendMessage(room.roomId, { role : "user", text : messageText, referencedText : referencedText || "" });
        applyFirstMessageTitle(room.roomId, messageText);
        return executeStreamTurnAsync(room, messageText, referencedText);
    }, [appendMessage, applyFirstMessageTitle, executeStreamTurnAsync]);

    return { isStreaming, streamingState, sendMessageAsync, executeStreamTurnAsync, stopStreaming };
}
