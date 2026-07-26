import { useEffect }       from "react";
import { useLayoutEffect } from "react";
import { useRef }          from "react";
import { useState }        from "react";

import AgentMessage          from "./AgentMessage";
import StreamingAgentMessage from "./StreamingAgentMessage";
import UserMessage           from "./UserMessage";

const NEAR_BOTTOM_THRESHOLD_PIXEL = 150;

/* 중앙 대화창.
   메시지 배열을 순회하면서 사용자 질문 순번(질문 수정용)과 답변 순번(북마크 식별용)을 함께 계산한다. */

export default function ChatMessageList({
    room, messageList, streamingState, isStreaming, isDeveloperMode,
    isBookmarked, onToggleBookmark, onSubmitEdit, onBlockedEdit, onRetryError, scrollTargetAgentIndex,
    isSpeechSupported, speakingKey, onToggleSpeak
}) {
    const feedRef              = useRef(null);
    const isPinnedToBottomRef  = useRef(true);   // 사용자가 위로 스크롤했으면 스트리밍이 따라가지 않는다
    const [highlightedAgentIndex, setHighlightedAgentIndex] = useState(null);

    const activeRoomId    = room?.roomId ?? null;
    const messageCount    = messageList?.length ?? 0;
    const streamingText   = streamingState?.text ?? "";
    const streamingReason = streamingState?.reasoning ?? "";

    const onFeedScroll = () => {
        const feedElement = feedRef.current;
        if (!feedElement) return;
        isPinnedToBottomRef.current =
            feedElement.scrollHeight - feedElement.scrollTop - feedElement.clientHeight < NEAR_BOTTOM_THRESHOLD_PIXEL;
    };

    // 방 전환 : 항상 하단으로 (고정 상태도 초기화)
    useLayoutEffect(() => {
        const feedElement = feedRef.current;
        if (!feedElement) return;
        isPinnedToBottomRef.current = true;
        feedElement.scrollTop = feedElement.scrollHeight;
    }, [activeRoomId]);

    // 새 메시지 / 스트리밍 청크 : 하단 근처에 있을 때만 따라간다
    useLayoutEffect(() => {
        const feedElement = feedRef.current;
        if (!feedElement || !isPinnedToBottomRef.current) return;
        feedElement.scrollTop = feedElement.scrollHeight;
    }, [messageCount, streamingText, streamingReason]);

    // 북마크에서 이동 : 대상 말풍선으로 스크롤하고 2초간 강조한다
    useEffect(() => {
        if (scrollTargetAgentIndex === null || scrollTargetAgentIndex === undefined) return;
        const feedElement = feedRef.current;
        if (!feedElement) return;

        let remainingAttemptCount = 20;
        let retryTimerId          = null;

        // 방 전환 직후에는 서버 복원이 비동기로 끝나므로, 대상 말풍선이 나타날 때까지 짧게 재시도한다
        const tryScrollToTarget = () => {
            const targetRow = feedElement.querySelector(`[data-agent-index="${scrollTargetAgentIndex}"]`);
            if (!targetRow) {
                if (remainingAttemptCount > 0) { remainingAttemptCount -= 1; retryTimerId = setTimeout(tryScrollToTarget, 100); }
                return;
            }
            isPinnedToBottomRef.current = false;
            targetRow.scrollIntoView({ behavior : "smooth", block : "center" });
            setHighlightedAgentIndex(scrollTargetAgentIndex);
            retryTimerId = setTimeout(() => setHighlightedAgentIndex(null), 2000);
        };
        tryScrollToTarget();

        return () => { if (retryTimerId !== null) clearTimeout(retryTimerId); };
    }, [scrollTargetAgentIndex, activeRoomId]);

    /* ── 본문 ── */

    if (!room) return <div className="chat-scroll flex-1 overflow-y-auto px-4 md:px-6 py-5" />;

    if (messageList === null) {
        // 다른 기기/재접속으로 로컬 캐시가 없는 방 : 서버(LangGraph 체크포인트)에서 복원 중
        return (
            <div className="chat-scroll flex-1 overflow-y-auto px-4 md:px-6 py-5">
                <div className="text-center pt-10 text-slate-400 dark:text-slate-600 text-sm">대화 내용을 불러오는 중…</div>
            </div>
        );
    }

    let userMessageIndex  = 0;   // 사용자 메시지 순번 : 질문 수정 시 체크포인트 절단 위치로 쓰인다
    let agentMessageIndex = 0;   // 답변 순번 : 북마크 식별·이동 대상 (에러 말풍선은 순번을 쓰지 않는다)

    const messageElementList = messageList.map((storedMessage, messageIndex) => {
        if (storedMessage.role === "user") {
            const currentUserMessageIndex = userMessageIndex++;
            return (
                <UserMessage key={messageIndex} text={storedMessage.text} userMessageIndex={currentUserMessageIndex}
                             isStreaming={isStreaming} onSubmitEdit={onSubmitEdit} onBlockedEdit={onBlockedEdit} />
            );
        }

        if (storedMessage.role === "error") {
            return (
                <div key={messageIndex} className="flex justify-start bubble-enter">
                    <div className="max-w-[78%] md:max-w-[65%] bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700/60 rounded-2xl rounded-bl-md px-4 py-2.5 text-sm leading-relaxed shadow">
                        <span className="whitespace-pre-wrap text-red-500 dark:text-red-400">{storedMessage.text}</span>
                        {storedMessage.retryMessageText ? (
                            <button onClick={() => onRetryError(storedMessage)}
                                    className="mt-2 block px-3 py-1.5 rounded-lg text-[11px] font-medium bg-red-100 hover:bg-red-200 text-red-700 dark:bg-red-950/60 dark:hover:bg-red-900/60 dark:text-red-300 border border-red-300 dark:border-red-800 transition">
                                ↻ 다시 시도
                            </button>
                        ) : null}
                    </div>
                </div>
            );
        }

        const currentAgentIndex = agentMessageIndex++;
        // 낭독 식별 키 : 방을 옮겨도 같은 순번이 겹치지 않도록 방 ID 를 함께 묶는다
        const speechKey = `${room.roomId}:${currentAgentIndex}`;
        return (
            <AgentMessage key={messageIndex} message={storedMessage} agentIndex={currentAgentIndex}
                          isBookmarked={isBookmarked(room.roomId, currentAgentIndex)}
                          onToggleBookmark={() => onToggleBookmark(room.roomId, currentAgentIndex, storedMessage.text, storedMessage.meta?.completed_at)}
                          isDeveloperMode={isDeveloperMode}
                          isHighlighted={highlightedAgentIndex === currentAgentIndex}
                          isSpeechSupported={isSpeechSupported}
                          isSpeaking={speakingKey === speechKey}
                          onToggleSpeak={(speechText) => onToggleSpeak(speechKey, speechText)} />
        );
    });

    const isEmptyFeed = messageCount === 0 && !streamingState;

    return (
        <div ref={feedRef} onScroll={onFeedScroll}
             className="chat-scroll flex-1 overflow-y-auto px-4 md:px-6 py-5 space-y-4">
            {isEmptyFeed ? (
                <div className="text-center pt-10">
                    <p className="text-slate-400 dark:text-slate-600 text-sm">메시지를 보내 오케스트레이터와 대화를 시작하세요.</p>
                    <p className="text-slate-400/80 dark:text-slate-700 text-[11px] mt-1.5">
                        백엔드 : <code className="font-mono">python src/server.py</code> (포트 8000)
                    </p>
                </div>
            ) : messageElementList}

            {streamingState ? <StreamingAgentMessage streamingState={streamingState} /> : null}
        </div>
    );
}
