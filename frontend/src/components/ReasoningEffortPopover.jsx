import { useEffect } from "react";
import { useRef }    from "react";

import { GearIcon } from "./icons";

/* 톱니바퀴 설정 : 생각 정도(reasoning effort)를 고른다 — 답하기 전에 얼마나 오래 생각할지.
   ollama 는 think 레벨, google 은 thinking_budget 으로 전달된다.
   입력창을 좁히지 않도록 드롭다운을 밖으로 빼고 필요할 때만 펼친다.

   값은 방(room)별로 저장된다. 끄면 빈 값이 되어 모델 기본 동작을 따른다. */

const EFFORT_OPTION_LIST = [
    { value : "low",    label : "낮음", descriptionText : "생각을 줄여 빠르게 답한다" },
    { value : "medium", label : "보통", descriptionText : "대부분의 대화에 적합하다" },
    { value : "high",   label : "높음", descriptionText : "오래 생각해 깊이 있게 답한다" }
];

const DEFAULT_EFFORT_VALUE = "medium";   // 껐다 켤 때 되돌아갈 값 (직전 선택이 없을 때)

export default function ReasoningEffortPopover({ isOpen, onToggleOpen, reasoningEffort, onReasoningEffortChange, isDisabled }) {
    const containerRef = useRef(null);
    // 껐다 켜도 직전에 고른 값으로 돌아오게 기억해 둔다 (끄는 순간 실제 값은 "" 가 되므로 별도 보관이 필요하다)
    const lastEffortRef = useRef(reasoningEffort || DEFAULT_EFFORT_VALUE);
    if (reasoningEffort) lastEffortRef.current = reasoningEffort;

    const isEffortEnabled = Boolean(reasoningEffort);

    // 바깥 클릭·ESC 로 닫는다 (열려 있을 때만 리스너를 건다)
    useEffect(() => {
        if (!isOpen) return undefined;

        const handlePointerDown = (event) => {
            if (containerRef.current && !containerRef.current.contains(event.target)) onToggleOpen(false);
        };
        const handleKeyDown = (event) => {
            if (event.key === "Escape") onToggleOpen(false);
        };

        document.addEventListener("mousedown", handlePointerDown);
        document.addEventListener("keydown", handleKeyDown);
        return () => {
            document.removeEventListener("mousedown", handlePointerDown);
            document.removeEventListener("keydown", handleKeyDown);
        };
    }, [isOpen, onToggleOpen]);

    return (
        <div ref={containerRef} className="relative shrink-0">
            <button type="button" onClick={() => onToggleOpen(!isOpen)}
                    disabled={isDisabled}
                    title="생각 정도 설정"
                    aria-label="생각 정도 설정"
                    aria-expanded={isOpen}
                    aria-haspopup="dialog"
                    className={`relative w-11 h-11 rounded-xl flex items-center justify-center transition border disabled:opacity-50 disabled:cursor-not-allowed ${
                        isOpen
                            ? "bg-indigo-50 dark:bg-indigo-950/60 border-indigo-400 dark:border-indigo-600 text-indigo-600 dark:text-indigo-400"
                            : "bg-white dark:bg-slate-950 border-slate-300 dark:border-slate-700 text-slate-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 hover:border-indigo-400 dark:hover:border-indigo-600"}`}>
                <GearIcon />
                {/* 지정했을 때만 점을 찍는다 — 아이콘만으로는 모델 기본인지 아닌지 알 수 없다 */}
                {isEffortEnabled ? (
                    <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-indigo-500 border-2 border-white dark:border-slate-950" aria-hidden="true" />
                ) : null}
            </button>

            {isOpen ? (
                <div role="dialog" aria-label="생각 정도 설정"
                     className="absolute bottom-full right-0 mb-2 w-72 p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 shadow-xl shadow-slate-300/40 dark:shadow-black/50 z-30">

                    <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                            <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">생각 정도</p>
                            <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">끄면 모델 기본 동작을 따릅니다</p>
                        </div>
                        <button onClick={() => onReasoningEffortChange(isEffortEnabled ? "" : lastEffortRef.current)}
                                role="switch" aria-checked={isEffortEnabled} aria-label="생각 정도 지정"
                                className={`shrink-0 relative w-9 h-5 rounded-full transition-colors ${isEffortEnabled ? "bg-indigo-600" : "bg-slate-300 dark:bg-slate-700"}`}>
                            <span className="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform"
                                  style={{ transform : isEffortEnabled ? "translateX(16px)" : "translateX(0)" }} />
                        </button>
                    </div>

                    {isEffortEnabled ? (
                        <div className="mt-3 space-y-1.5">
                            {EFFORT_OPTION_LIST.map(effortOption => (
                                <button key={effortOption.value} onClick={() => onReasoningEffortChange(effortOption.value)}
                                        className={`w-full text-left px-3 py-2 rounded-lg border transition ${
                                            reasoningEffort === effortOption.value
                                                ? "bg-indigo-50 dark:bg-indigo-950/60 border-indigo-400 dark:border-indigo-600"
                                                : "bg-white dark:bg-slate-950 border-slate-200 dark:border-slate-800 hover:border-indigo-300 dark:hover:border-indigo-700"}`}>
                                    <span className={`block text-xs font-semibold ${
                                        reasoningEffort === effortOption.value ? "text-indigo-600 dark:text-indigo-400" : "text-slate-700 dark:text-slate-300"}`}>
                                        {effortOption.label}
                                    </span>
                                    <span className="block text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">{effortOption.descriptionText}</span>
                                </button>
                            ))}
                        </div>
                    ) : null}
                </div>
            ) : null}
        </div>
    );
}
