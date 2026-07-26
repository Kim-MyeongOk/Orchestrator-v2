import { useEffect } from "react";
import { useRef }    from "react";

import { SendIcon } from "./icons";
import { StopIcon } from "./icons";

const TEXTAREA_MAXIMUM_HEIGHT_PIXEL = 160;

/* 하단 입력 바 : Enter 전송 / Shift+Enter 줄바꿈 · 자동 높이 · 스트리밍 중에는 중단 버튼으로 전환 */

export default function ChatInput({ inputValue, onInputValueChange, onSend, onStop, isStreaming }) {
    const textareaRef = useRef(null);

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
        }
    };

    return (
        <footer className="shrink-0 border-t border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/60 backdrop-blur p-3 md:p-4">
            <div className="max-w-3xl mx-auto flex items-end gap-2.5">
                <textarea ref={textareaRef} rows={1} value={inputValue}
                          onChange={(event) => onInputValueChange(event.target.value)}
                          onKeyDown={onKeyDown}
                          placeholder="메시지 입력…  (Enter 전송 · Shift+Enter 줄바꿈)"
                          className="flex-1 bg-white dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-4 py-3 text-sm resize-none max-h-40 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 transition placeholder:text-slate-400 dark:placeholder:text-slate-600" />
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
