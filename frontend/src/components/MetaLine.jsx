import { useEffect } from "react";
import { useState }  from "react";

import { formatFullTimestamp } from "../utils/time";
import { formatRelativeTime }  from "../utils/time";
import { useTimeTick }         from "../utils/time";

const META_LINE_CLASS = "text-[11px] text-slate-500 dark:text-slate-600 font-mono";

function formatTokenMetaText(elapsedSecondText, reasoningTokenCount, answerTokenCount) {
    return `⏱ ${elapsedSecondText}s · 생각 ${reasoningTokenCount} 토큰 · 응답 ${answerTokenCount} 토큰`;
}

/* 완료된 답변의 메타라인
     - 개발자 모드 : 절대 시각(ms) + 경과·토큰 메타
     - 일반 모드   : 상대 시간 (30초 주기로 자동 갱신) */

export function CompletedMetaLine({ meta, isDeveloperMode }) {
    useTimeTick();   // 30초마다 상대 시간을 다시 계산한다

    if (!meta) return null;

    const tokenMetaText = formatTokenMetaText(meta.elapsed_second_text, meta.reasoning_token_count, meta.answer_token_count);

    // 레거시(완료 시각 미저장) : 기존 토큰 메타만 고정 표시
    if (!meta.completed_at) return <div className={META_LINE_CLASS}>{tokenMetaText}</div>;

    return (
        <div className={META_LINE_CLASS}>
            {isDeveloperMode ? `${formatFullTimestamp(meta.completed_at)} · ${tokenMetaText}` : formatRelativeTime(meta.completed_at)}
        </div>
    );
}

/* 스트리밍 중 메타라인 : 0.1초 간격으로 경과 시간을 갱신한다 (클로드식 실시간 카운터).
   이 컴포넌트만 리렌더되도록 분리해 두어 말풍선 본문은 토큰 도착 시에만 다시 그린다. */

export function LiveMetaLine({ startedAt, reasoningTokenCount, answerTokenCount }) {
    const [elapsedSecondText, setElapsedSecondText] = useState("0.0");

    useEffect(() => {
        const updateElapsed = () => setElapsedSecondText(((performance.now() - startedAt) / 1000).toFixed(1));
        updateElapsed();
        const timerId = setInterval(updateElapsed, 100);
        return () => clearInterval(timerId);
    }, [startedAt]);

    return <div className={META_LINE_CLASS}>{formatTokenMetaText(elapsedSecondText, reasoningTokenCount, answerTokenCount)}</div>;
}
