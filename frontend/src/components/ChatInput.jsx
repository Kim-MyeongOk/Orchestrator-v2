import { useEffect } from "react";
import { useRef }    from "react";

import { MicrophoneIcon } from "./icons";
import { SendIcon }       from "./icons";
import { SoundWaveIcon }  from "./icons";
import { StopIcon }       from "./icons";

const TEXTAREA_MAXIMUM_HEIGHT_PIXEL = 160;
const REFERENCE_PREVIEW_LENGTH      = 60;   // 태그 바에 보여줄 발췌 미리보기 길이

/* 하단 입력 바 : Enter 전송 / Shift+Enter 줄바꿈 · 자동 높이 · 스트리밍 중에는 중단 버튼으로 전환.
   답변에서 「참조하기」로 담은 발췌가 있으면 입력창 위에 태그 바로 표시한다.
   🎙 버튼으로 음성 받아쓰기를 켜면 인식 결과가 입력창에 실시간으로 채워진다. */

export default function ChatInput({ inputValue, onInputValueChange, onSend, onStop, isStreaming, referencedText, onClearReference, presetName, onPresetNameChange, availablePresetNames, isRecognitionSupported, isRecording, onToggleRecording }) {
    const textareaRef = useRef(null);

    // 참조를 담으면 바로 이어서 질문을 쓸 수 있게 입력창으로 포커스를 옮긴다
    useEffect(() => {
        if (referencedText) textareaRef.current?.focus();
    }, [referencedText]);

    // 자동 높이 : 값이 바뀔 때마다 scrollHeight 로 재계산한다 (전송 후 초기화도 여기서 처리된다)
    useEffect(() => {
        const textareaElement = textareaRef.current;
        if (!textareaElement) return;
        textareaElement.style.height = "auto";
        textareaElement.style.height = `${Math.min(textareaElement.scrollHeight, TEXTAREA_MAXIMUM_HEIGHT_PIXEL)}px`;
    }, [inputValue]);

    // 스트리밍이 끝나면 입력창으로 포커스를 되돌린다
    useEffect(() => {
        if (!isStreaming) textareaRef.current?.focus();
    }, [isStreaming]);

    const onKeyDown = (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            onSend();
            return;
        }
        // 입력이 비어 있을 때의 Backspace 로도 참조를 뗄 수 있게 한다 (❌ 를 겨냥하지 않아도 되도록)
        if (event.key === "Backspace" && inputValue === "" && referencedText) {
            event.preventDefault();
            onClearReference();
        }
    };

    const referencePreviewText = (referencedText || "").replace(/\s+/g, " ").trim();
    const isPreviewTruncated   = referencePreviewText.length > REFERENCE_PREVIEW_LENGTH;

    return (
        <footer className="shrink-0 border-t border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/60 backdrop-blur p-3 md:p-4">
            {/* 참조 태그 바 : [참조: "선택 텍스트…"] ❌ */}
            {referencedText ? (
                <div className="max-w-3xl mx-auto mb-2 flex">
                    <div className="flex items-center gap-1.5 max-w-full min-w-0 pl-2.5 pr-1.5 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/50 border border-indigo-200 dark:border-indigo-800 text-indigo-700 dark:text-indigo-300">
                        <span className="shrink-0 text-[11px] font-semibold">참조</span>
                        <span className="min-w-0 truncate text-[11px]" title={referencedText}>
                            “{referencePreviewText.slice(0, REFERENCE_PREVIEW_LENGTH)}{isPreviewTruncated ? "…" : ""}”
                        </span>
                        <button type="button" onClick={onClearReference} title="참조 해제" aria-label="참조 해제"
                                className="shrink-0 w-4 h-4 rounded flex items-center justify-center text-indigo-400 dark:text-indigo-500 hover:text-red-500 dark:hover:text-red-400 transition text-[10px]">
                            ✕
                        </button>
                    </div>
                </div>
            ) : null}

            <div className="max-w-3xl mx-auto flex items-end gap-2.5">
                <textarea ref={textareaRef} rows={1} value={inputValue}
                          onChange={(event) => onInputValueChange(event.target.value)}
                          onKeyDown={onKeyDown}
                          placeholder={isRecording ? "듣고 있습니다…  말씀하세요" : "메시지 입력…  (Enter 전송 · Shift+Enter 줄바꿈)"}
                          className={`flex-1 bg-white dark:bg-slate-950 border rounded-xl px-4 py-3 text-sm resize-none max-h-40 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 transition placeholder:text-slate-400 dark:placeholder:text-slate-600 ${
                              isRecording ? "border-red-400 dark:border-red-500" : "border-slate-300 dark:border-slate-700"}`} />

                {/* 음성 받아쓰기 : 미지원 브라우저(Firefox 등)에서는 버튼 자체를 감춘다 */}
                {isRecognitionSupported ? (
                    <button type="button" onClick={onToggleRecording}
                            title={isRecording ? "음성 입력 중지" : "음성으로 입력"}
                            aria-label={isRecording ? "음성 입력 중지" : "음성으로 입력"}
                            aria-pressed={isRecording}
                            className={`relative shrink-0 w-11 h-11 rounded-xl flex items-center justify-center transition border ${
                                isRecording
                                    ? "bg-red-600 border-red-600 text-white hover:bg-red-500"
                                    : "bg-white dark:bg-slate-950 border-slate-300 dark:border-slate-700 text-slate-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 hover:border-indigo-400 dark:hover:border-indigo-600"}`}>
                        {/* 인식 중에는 버튼 밖으로 붉은 파문이 퍼진다 */}
                        {isRecording ? <span className="absolute inset-0 rounded-xl bg-red-500/60 animate-ping" aria-hidden="true" /> : null}
                        <span className="relative">{isRecording ? <SoundWaveIcon /> : <MicrophoneIcon />}</span>
                    </button>
                ) : null}

                {/* LLM 파라미터 프리셋 선택 드롭다운 */}
                {availablePresetNames && availablePresetNames.length > 0 ? (
                    <select value={presetName || "MEDIUM"} onChange={(event) => onPresetNameChange(event.target.value)}
                            title="LLM 파라미터 프리셋 선택 (LOW: 저온도, MEDIUM: 표준, HIGH: 높은 창의성)"
                            className="shrink-0 px-3 py-2.5 rounded-xl bg-white dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-sm font-medium text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 transition hover:bg-slate-50 dark:hover:bg-slate-900">
                        {availablePresetNames.map(name => (
                            <option key={name} value={name}>{name}</option>
                        ))}
                    </select>
                ) : null}
                <button onClick={isStreaming ? onStop : onSend}
                        title={isStreaming ? "응답 중단" : "전송"}
                        aria-label={isStreaming ? "응답 중단" : "전송"}
                        className={`shrink-0 w-11 h-11 rounded-xl text-white flex items-center justify-center transition shadow-lg shadow-indigo-200 dark:shadow-indigo-950/50 ${
                            isStreaming ? "bg-red-600 hover:bg-red-500" : "bg-indigo-600 hover:bg-indigo-500"}`}>
                    {isStreaming ? <StopIcon /> : <SendIcon />}
                </button>
            </div>
        </footer>
    );
}
