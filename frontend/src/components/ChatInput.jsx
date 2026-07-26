import { useEffect } from "react";
import { useRef }    from "react";

import { MicrophoneIcon } from "./icons";
import { SendIcon }       from "./icons";
import { SoundWaveIcon }  from "./icons";
import { StopIcon }       from "./icons";

const TEXTAREA_MAXIMUM_HEIGHT_PIXEL = 160;
const REFERENCE_PREVIEW_LENGTH      = 60;   // 태그 바에 보여줄 발췌 미리보기 길이

/* 하단 입력 바 : Enter 전송 / Shift+Enter 줄바꿈 · 자동 높이 · 스트리밍 중에는 중단 버튼으로 전환.
   입력창 위 칩 바에는 두 종류의 참조가 함께 놓인다.
     ❝ 발췌   : 답변 본문을 드래그해 담은 문장 일부 (한 번에 하나)
     📌 답변 #N : 답변을 우클릭해 통째로 담은 것 (여러 개)
   🎙 버튼으로 음성 받아쓰기를 켜면 인식 결과가 입력창에 실시간으로 채워진다. */

export default function ChatInput({ inputValue, onInputValueChange, onSend, onStop, isStreaming, referencedText, onClearReference, presetName, onPresetNameChange, availablePresetNames, isRecognitionSupported, isRecording, onToggleRecording, selectedReferenceList, onRemoveReference, onClearAllReferences }) {
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

    const referencePreviewText = (referencedText || "").replace(/\s+/g, " ").trim();
    const isPreviewTruncated   = referencePreviewText.length > REFERENCE_PREVIEW_LENGTH;
    const referenceChipList    = selectedReferenceList || [];
    const hasAnyReference      = !!referencedText || referenceChipList.length > 0;

    const onKeyDown = (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            onSend();
            return;
        }
        // 입력이 비어 있을 때의 Backspace 로도 참조를 뗄 수 있게 한다 (✕ 를 겨냥하지 않아도 되도록)
        // 마지막에 담은 것부터 하나씩 뗀다 — 발췌가 있으면 발췌를, 없으면 답변 참조의 끝에서부터.
        if (event.key === "Backspace" && inputValue === "") {
            if (referencedText) {
                event.preventDefault();
                onClearReference();
            } else if (referenceChipList.length > 0) {
                event.preventDefault();
                onRemoveReference(referenceChipList[referenceChipList.length - 1].agentIndex);
            }
        }
    };

    return (
        <footer className="shrink-0 border-t border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/60 backdrop-blur p-3 md:p-4">
            {/* 참조 칩 바 : ❝ 드래그 발췌 1개 + 📌 답변 참조 여러 개 */}
            {hasAnyReference ? (
                <div className="max-w-3xl mx-auto mb-2 flex flex-wrap items-center gap-1.5">
                    {referencedText ? (
                        <div className="flex items-center gap-1.5 max-w-full min-w-0 pl-2.5 pr-1.5 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/50 border border-indigo-200 dark:border-indigo-800 text-indigo-700 dark:text-indigo-300">
                            <span className="shrink-0 text-[11px] font-semibold">❝ 발췌</span>
                            <span className="min-w-0 truncate text-[11px]" title={referencedText}>
                                “{referencePreviewText.slice(0, REFERENCE_PREVIEW_LENGTH)}{isPreviewTruncated ? "…" : ""}”
                            </span>
                            <button type="button" onClick={onClearReference} title="발췌 참조 해제" aria-label="발췌 참조 해제"
                                    className="shrink-0 w-4 h-4 rounded flex items-center justify-center text-indigo-400 dark:text-indigo-500 hover:text-red-500 dark:hover:text-red-400 transition text-[10px]">
                                ✕
                            </button>
                        </div>
                    ) : null}

                    {referenceChipList.map(reference => (
                        <div key={reference.messageId}
                             className="flex items-center gap-1 max-w-full min-w-0 pl-2 pr-1 py-1 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 text-amber-800 dark:text-amber-300">
                            {/* 미리보기를 title 로 붙여 어떤 답변인지 번호만 보고 헷갈리지 않게 한다 */}
                            <span className="shrink-0 text-[11px] font-semibold" title={reference.previewText}>
                                📌 답변 #{reference.agentIndex + 1}
                            </span>
                            <button type="button" onClick={() => onRemoveReference(reference.agentIndex)}
                                    title={`답변 #${reference.agentIndex + 1} 참조 해제`} aria-label={`답변 #${reference.agentIndex + 1} 참조 해제`}
                                    className="shrink-0 w-4 h-4 rounded flex items-center justify-center text-amber-500 dark:text-amber-600 hover:text-red-500 dark:hover:text-red-400 transition text-[10px]">
                                ✕
                            </button>
                        </div>
                    ))}

                    {/* 참조가 2개를 넘어가면 하나씩 빼기가 번거로워진다 */}
                    {referenceChipList.length + (referencedText ? 1 : 0) > 2 ? (
                        <button type="button" onClick={onClearAllReferences}
                                className="shrink-0 px-2 py-1 rounded-lg text-[11px] text-slate-500 dark:text-slate-400 hover:text-red-500 dark:hover:text-red-400 hover:bg-slate-200/70 dark:hover:bg-slate-800/60 transition">
                            전체 해제
                        </button>
                    ) : null}
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
