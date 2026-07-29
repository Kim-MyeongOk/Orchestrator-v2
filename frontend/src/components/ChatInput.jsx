import { useEffect } from "react";
import { useRef }    from "react";
import { useState }  from "react";

import ReasoningEffortPopover from "./ReasoningEffortPopover";

import { MicrophoneIcon } from "./icons";
import { PaperclipIcon }  from "./icons";
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

export default function ChatInput({ inputValue, onInputValueChange, onSend, onStop, isStreaming, referencedText, onClearReference, reasoningEffort, onReasoningEffortChange, isEffortSettingsOpen, onToggleEffortSettingsOpen, isEffortSettingsDisabled, isRecognitionSupported, isRecording, onToggleRecording, selectedReferenceList, onRemoveReference, onClearAllReferences, attachedImageList, isUploadingImage, onAttachImageFileList, onRemoveImage, isVisionSupported, activeModelName }) {
    const textareaRef  = useRef(null);
    const fileInputRef = useRef(null);

    // 드래그가 자식 요소로 넘어갈 때마다 leave 가 발생해 테두리가 깜빡인다.
    // enter/leave 횟수를 세어 0 이 될 때만 강조를 푼다.
    const dragDepthRef = useRef(0);
    const [isDragOver, setIsDragOver] = useState(false);

    const onPickFileClick = () => fileInputRef.current?.click();

    const onFileInputChange = (event) => {
        onAttachImageFileList([...event.target.files]);
        event.target.value = "";   // 같은 파일을 다시 골라도 change 가 나도록 비운다
    };

    /* ── 드래그앤드롭 ── */

    const onDragEnter = (event) => {
        if (![...event.dataTransfer.types].includes("Files")) return;   // 텍스트 드래그는 무시
        event.preventDefault();
        dragDepthRef.current += 1;
        setIsDragOver(true);
    };

    const onDragOver = (event) => {
        if (![...event.dataTransfer.types].includes("Files")) return;
        event.preventDefault();   // 막지 않으면 브라우저가 파일을 새 탭으로 열어버린다
    };

    const onDragLeave = () => {
        dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
        if (dragDepthRef.current === 0) setIsDragOver(false);
    };

    const onDrop = (event) => {
        event.preventDefault();
        dragDepthRef.current = 0;
        setIsDragOver(false);
        onAttachImageFileList([...event.dataTransfer.files]);
    };

    // 클립보드 붙여넣기(스크린샷 Ctrl+V)도 같은 경로로 받는다
    const onPaste = (event) => {
        const pastedFileList = [...event.clipboardData.files];
        if (pastedFileList.length === 0) return;
        event.preventDefault();
        onAttachImageFileList(pastedFileList);
    };

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

    const imageList = attachedImageList || [];

    return (
        <footer onDragEnter={onDragEnter} onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}
                className={`relative shrink-0 border-t bg-white/70 dark:bg-slate-900/60 backdrop-blur p-3 md:p-4 transition ${
                    isDragOver ? "border-indigo-400 dark:border-indigo-500" : "border-slate-200 dark:border-slate-800"}`}>

            {/* 드래그 중 오버레이 : 어디에 놓아도 된다는 것을 보여준다 */}
            {isDragOver ? (
                <div className="absolute inset-0 z-10 flex items-center justify-center rounded-t-xl bg-indigo-50/90 dark:bg-indigo-950/80 border-2 border-dashed border-indigo-400 dark:border-indigo-500 pointer-events-none">
                    <span className="text-sm font-medium text-indigo-600 dark:text-indigo-300">🖼 이미지를 여기에 놓으세요</span>
                </div>
            ) : null}

            {/* 첨부 이미지 썸네일 : 업로드 중에는 흐리게 + 스피너, 실패하면 빨간 테두리 */}
            {imageList.length > 0 ? (
                <div className="max-w-3xl mx-auto mb-2 flex flex-wrap gap-2">
                    {imageList.map(attachedImage => (
                        <div key={attachedImage.attachmentId}
                             className={`relative w-16 h-16 rounded-lg overflow-hidden border bg-slate-100 dark:bg-slate-800 ${
                                 attachedImage.errorText ? "border-red-400 dark:border-red-500" : "border-slate-300 dark:border-slate-700"}`}
                             title={attachedImage.errorText || attachedImage.fileName}>
                            <img src={attachedImage.previewUrl} alt={attachedImage.fileName}
                                 className={`w-full h-full object-cover ${attachedImage.isUploading || attachedImage.errorText ? "opacity-40" : ""}`} />
                            {attachedImage.isUploading ? (
                                <span className="absolute inset-0 flex items-center justify-center text-[10px] font-medium text-slate-600 dark:text-slate-300">
                                    업로드 중…
                                </span>
                            ) : null}
                            {attachedImage.errorText ? (
                                <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-red-600 dark:text-red-400">실패</span>
                            ) : null}
                            <button type="button" onClick={() => onRemoveImage(attachedImage.attachmentId)}
                                    title="이미지 제거" aria-label={`${attachedImage.fileName} 제거`}
                                    className="absolute top-0.5 right-0.5 w-4 h-4 rounded-full bg-slate-900/70 text-white text-[10px] flex items-center justify-center hover:bg-red-600 transition">
                                ✕
                            </button>
                        </div>
                    ))}
                </div>
            ) : null}
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
                {/* 이미지 첨부 : 파일 선택 (드래그앤드롭·붙여넣기도 같은 경로로 처리된다) */}
                <input ref={fileInputRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif"
                       multiple hidden onChange={onFileInputChange} />
                {/* 비전 미지원 모델에서도 잠그지 않는다 — 첨부하면 비전 모델로 자동 전환된다 */}
                <button type="button" onClick={onPickFileClick} disabled={isUploadingImage}
                        title={isVisionSupported
                            ? "이미지 첨부 (드래그앤드롭·붙여넣기 가능)"
                            : `이미지 첨부 (${activeModelName} 은 이미지를 못 읽어 비전 모델로 자동 전환됩니다)`}
                        aria-label="이미지 첨부"
                        className="shrink-0 w-11 h-11 rounded-xl flex items-center justify-center transition border bg-white dark:bg-slate-950 border-slate-300 dark:border-slate-700 text-slate-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 hover:border-indigo-400 dark:hover:border-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed">
                    <PaperclipIcon />
                </button>

                <textarea ref={textareaRef} rows={1} value={inputValue}
                          onChange={(event) => onInputValueChange(event.target.value)}
                          onKeyDown={onKeyDown}
                          onPaste={onPaste}
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

                {/* 생각 정도 설정 : 드롭다운을 상시 노출하지 않고 톱니바퀴 안으로 넣는다 */}
                <ReasoningEffortPopover isOpen={isEffortSettingsOpen} onToggleOpen={onToggleEffortSettingsOpen}
                                        reasoningEffort={reasoningEffort} onReasoningEffortChange={onReasoningEffortChange}
                                        isDisabled={isEffortSettingsDisabled} />
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
