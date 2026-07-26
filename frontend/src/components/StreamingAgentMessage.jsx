import { useEffect } from "react";
import { useState }  from "react";

import { LiveMetaLine } from "./MetaLine";

/* 스트리밍 중인 답변 말풍선.
   완료본(AgentMessage)과 달리 마크다운을 렌더링하지 않고 원문을 whitespace-pre-wrap 으로 흘려보낸다
   (파싱 중인 마크다운이 깜빡이는 것을 막고, 토큰당 파싱 비용도 아낀다). */

export default function StreamingAgentMessage({ streamingState }) {
    const { text, reasoning, reasoningTokenCount, answerTokenCount, startedAt, retryNoticeText } = streamingState;

    const hasAnswerText = text !== "";

    // 첫 조각에서 자동으로 펼치고 답변 본문이 시작되면 접는다.
    // 사용자가 직접 접었다 폈다 한 것을 스트리밍 리렌더가 되돌리지 않도록 상태로 들고 있는다.
    const [isReasoningOpen, setIsReasoningOpen] = useState(true);
    useEffect(() => { if (hasAnswerText) setIsReasoningOpen(false); }, [hasAnswerText]);

    return (
        <div className="flex justify-start bubble-enter">
            <div className="flex flex-col items-start max-w-[78%] md:max-w-[65%]">
                <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700/60 rounded-2xl rounded-bl-md px-4 py-2.5 text-sm leading-relaxed shadow w-fit min-w-0 transition">
                    {reasoning ? (
                        <details className="mb-1.5 -mx-1" open={isReasoningOpen}
                                 onToggle={(event) => setIsReasoningOpen(event.currentTarget.open)}>
                            <summary className="cursor-pointer select-none text-[11px] text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition px-1">
                                🤔 생각 과정{" "}
                                {!hasAnswerText
                                    ? <span className="text-slate-400 dark:text-slate-600">(생각 중… {reasoningTokenCount} 토큰)</span>
                                    : null}
                            </summary>
                            <div className="chat-scroll whitespace-pre-wrap text-[11px] leading-relaxed text-slate-500 bg-slate-100 dark:bg-slate-950/50 border border-slate-200 dark:border-slate-800 rounded-lg px-2.5 py-2 mt-1 max-h-36 overflow-y-auto">
                                {reasoning}
                            </div>
                        </details>
                    ) : null}

                    {retryNoticeText
                        ? <span className="text-[11px] text-amber-600 dark:text-amber-400 italic">{retryNoticeText}</span>
                        : null}

                    {/* 첫 토큰 전에는 타이핑 인디케이터를 보여준다 */}
                    {!hasAnswerText && !reasoning && !retryNoticeText ? (
                        <span className="inline-flex gap-1 items-center py-1">
                            <span className="typing-dot w-1.5 h-1.5 rounded-full bg-slate-400" />
                            <span className="typing-dot w-1.5 h-1.5 rounded-full bg-slate-400" />
                            <span className="typing-dot w-1.5 h-1.5 rounded-full bg-slate-400" />
                        </span>
                    ) : null}

                    {hasAnswerText ? <span className="whitespace-pre-wrap">{text}</span> : null}
                </div>

                <div className="flex items-center gap-1.5 mt-1 px-1 min-h-5">
                    <LiveMetaLine startedAt={startedAt} reasoningTokenCount={reasoningTokenCount} answerTokenCount={answerTokenCount} />
                </div>
            </div>
        </div>
    );
}
