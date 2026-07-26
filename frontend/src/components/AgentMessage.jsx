import { useMemo }  from "react";
import { useState } from "react";

import { renderMarkdownToHtml }  from "../utils/markdown";
import { stripMarkdownForSpeech } from "../utils/markdown";
import { writeTextToClipboard }   from "../utils/markdown";
import { BookmarkIcon }           from "./icons";
import { CheckIcon }              from "./icons";
import { CopyIcon }               from "./icons";
import { SpeakerIcon }            from "./icons";
import { CompletedMetaLine }      from "./MetaLine";
import ReferenceableText          from "./ReferenceableText";

const TOOLTIP_CLASS = "pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2 py-1 rounded-md "
                    + "bg-slate-800 dark:bg-slate-700 text-white text-[11px] whitespace-nowrap shadow-lg opacity-0 group-hover:opacity-100 transition z-20";

/* 답변 원문(마크다운 소스)을 클립보드로 복사한다.
   툴팁은 버튼 "위"에 뜨는 커스텀 툴팁을 쓴다 (네이티브 title 은 커서 아래에 그려져 가려진다). */

function AnswerCopyButton({ answerText }) {
    const [isCopied, setIsCopied] = useState(false);

    const onCopyClick = async () => {
        await writeTextToClipboard(answerText);
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), 1500);
    };

    return (
        <span className="group relative shrink-0 inline-flex">
            <button type="button" onClick={onCopyClick} aria-label="메시지 복사"
                    className={`w-5 h-5 rounded flex items-center justify-center hover:bg-slate-200 dark:hover:bg-slate-800 transition ${
                        isCopied ? "text-emerald-500 dark:text-emerald-400"
                                 : "text-slate-400 dark:text-slate-500 hover:text-indigo-500 dark:hover:text-indigo-400"}`}>
                {isCopied ? <CheckIcon /> : <CopyIcon />}
            </button>
            <span className={TOOLTIP_CLASS}>{isCopied ? "복사됨" : "메시지 복사"}</span>
        </span>
    );
}

/* (방, 답변 순번) 으로 식별되는 북마크 토글 버튼 */

function AnswerBookmarkButton({ isActive, onToggle }) {
    return (
        <span className="group relative shrink-0 inline-flex">
            <button type="button" onClick={onToggle} aria-pressed={isActive} aria-label={isActive ? "북마크 해제" : "북마크"}
                    className={`w-5 h-5 rounded flex items-center justify-center hover:bg-slate-200 dark:hover:bg-slate-800 transition ${
                        isActive ? "text-indigo-500 dark:text-indigo-400"
                                 : "text-slate-400 dark:text-slate-500 hover:text-indigo-500 dark:hover:text-indigo-400"}`}>
                <BookmarkIcon isFilled={isActive} />
            </button>
            <span className={TOOLTIP_CLASS}>{isActive ? "북마크 해제" : "북마크"}</span>
        </span>
    );
}

/* 답변 낭독 토글 버튼 (재생 중이면 정지 아이콘으로 바뀐다) */

function AnswerSpeakButton({ isSpeaking, onToggle }) {
    return (
        <span className="group relative shrink-0 inline-flex">
            <button type="button" onClick={onToggle} aria-pressed={isSpeaking} aria-label={isSpeaking ? "낭독 정지" : "답변 낭독"}
                    className={`w-5 h-5 rounded flex items-center justify-center hover:bg-slate-200 dark:hover:bg-slate-800 transition ${
                        isSpeaking ? "text-indigo-500 dark:text-indigo-400"
                                   : "text-slate-400 dark:text-slate-500 hover:text-indigo-500 dark:hover:text-indigo-400"}`}>
                <SpeakerIcon isSpeaking={isSpeaking} />
            </button>
            <span className={TOOLTIP_CLASS}>{isSpeaking ? "낭독 정지" : "소리로 듣기"}</span>
        </span>
    );
}

/* 완료된 에이전트 답변 말풍선 : 생각 과정(접이식) + 마크다운 본문 + 하단 액션/메타 행 */

export default function AgentMessage({
    message, agentIndex, isBookmarked, onToggleBookmark, isDeveloperMode, isHighlighted,
    isSpeechSupported, isSpeaking, onToggleSpeak, onQuoteText, isReferenceSelected, onToggleReference
}) {
    const isEmptyAnswer = (message.text || "").trim() === "";
    const answerHtml    = useMemo(() => (isEmptyAnswer ? "" : renderMarkdownToHtml(message.text)), [message.text, isEmptyAnswer]);

    // 북마크 이동 강조(파랑)와 참조 선택(호박)은 서로 다른 뜻이라 색을 나눈다.
    // 둘이 겹치면 "지금 찾아온 답변" 쪽을 우선 보여준다 (강조는 2초 뒤 사라진다)
    const ringClass = isHighlighted        ? " ring-2 ring-indigo-400 dark:ring-indigo-500"
                    : isReferenceSelected  ? " ring-2 ring-amber-400 dark:ring-amber-500"
                    : "";

    // 빈 응답은 참조로 담아도 모델에 넘길 본문이 없다
    const isReferenceable = !isEmptyAnswer && agentIndex !== null && agentIndex !== undefined;

    const onBubbleContextMenu = (event) => {
        // 본문에서 텍스트를 드래그한 우클릭은 ReferenceableText 가 먼저 가로채고 전파를 끊는다.
        // 여기까지 온 우클릭은 "이 답변을 통째로 참조" 토글이다.
        if (!isReferenceable) return;
        event.preventDefault();
        onToggleReference();
    };

    return (
        <div className="flex justify-start bubble-enter" data-agent-index={agentIndex}>
            <div className="flex flex-col items-start max-w-[78%] md:max-w-[65%]">
                <div onContextMenu={onBubbleContextMenu}
                     title={isReferenceable ? "우클릭 : 이 답변을 참조로 담기/빼기" : undefined}
                     className={`relative bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700/60 rounded-2xl rounded-bl-md px-4 py-2.5 text-sm leading-relaxed shadow w-fit min-w-0 transition${ringClass}`}>
                    {/* 참조로 담긴 답변임을 말풍선 자체에 표시한다 (칩 바까지 내려가 확인하지 않아도 되도록) */}
                    {isReferenceSelected ? (
                        <span aria-hidden="true"
                              className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-amber-400 dark:bg-amber-500 text-white text-[10px] flex items-center justify-center shadow ring-2 ring-white dark:ring-slate-900">
                            📌
                        </span>
                    ) : null}
                    {message.reasoning ? (
                        <details className="mb-1.5 -mx-1">
                            <summary className="cursor-pointer select-none text-[11px] text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition px-1">
                                🤔 생각 과정
                            </summary>
                            <div className="chat-scroll whitespace-pre-wrap text-[11px] leading-relaxed text-slate-500 bg-slate-100 dark:bg-slate-950/50 border border-slate-200 dark:border-slate-800 rounded-lg px-2.5 py-2 mt-1 max-h-36 overflow-y-auto">
                                {message.reasoning}
                            </div>
                        </details>
                    ) : null}

                    {/* 본문만 참조 대상으로 감싼다 — 생각 과정은 모델의 중간 사고라 질문 문맥으로 담을 값이 아니다 */}
                    {isEmptyAnswer
                        ? <span className="text-slate-500 italic">(빈 응답 — 모델이 텍스트를 생성하지 않았습니다)</span>
                        : <ReferenceableText onQuote={onQuoteText}>
                              <span className="md-body" dangerouslySetInnerHTML={{ __html : answerHtml }} />
                          </ReferenceableText>}
                </div>

                <div className="flex items-center gap-1.5 mt-1 px-1 min-h-5">
                    <AnswerCopyButton answerText={message.text} />
                    {/* 낭독은 읽을 본문이 있을 때만 (빈 응답·미지원 브라우저에서는 버튼 자체를 숨긴다) */}
                    {isSpeechSupported && !isEmptyAnswer
                        ? <AnswerSpeakButton isSpeaking={isSpeaking}
                                             onToggle={() => onToggleSpeak(stripMarkdownForSpeech(message.text))} />
                        : null}
                    {agentIndex !== null && agentIndex !== undefined
                        ? <AnswerBookmarkButton isActive={isBookmarked} onToggle={onToggleBookmark} />
                        : null}
                    <CompletedMetaLine meta={message.meta} isDeveloperMode={isDeveloperMode} />
                </div>
            </div>
        </div>
    );
}
