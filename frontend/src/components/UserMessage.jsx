import { useEffect } from "react";
import { useRef }    from "react";
import { useState }  from "react";

/* 사용자 질문 말풍선.
   마우스를 올리면 수정 버튼이 나타나고, 수정하면 이 질문 이후의 대화를 지우고 여기서부터 다시 이어간다. */

export default function UserMessage({ text, referencedText, referencedAgentIndexList, imageUrlList, userMessageIndex, isStreaming, onSubmitEdit, onBlockedEdit }) {
    const [isEditing, setIsEditing]   = useState(false);
    const [draftText, setDraftText]   = useState(text);
    const textareaRef                 = useRef(null);

    useEffect(() => {
        if (!isEditing) return;
        const textareaElement = textareaRef.current;
        if (!textareaElement) return;
        textareaElement.focus();
        textareaElement.setSelectionRange(textareaElement.value.length, textareaElement.value.length);
    }, [isEditing]);

    const startEdit = () => {
        if (isStreaming) { onBlockedEdit(); return; }
        setDraftText(text);
        setIsEditing(true);
    };

    const submitEdit = () => {
        const trimmedText = draftText.trim();
        if (!trimmedText) return;
        setIsEditing(false);
        onSubmitEdit(userMessageIndex, trimmedText);
    };

    if (isEditing) {
        return (
            <div className="flex justify-end">
                <div className="w-full max-w-[85%] md:max-w-[72%] flex flex-col gap-2">
                    <textarea ref={textareaRef} rows={3} value={draftText}
                              onChange={(event) => setDraftText(event.target.value)}
                              onKeyDown={(event) => {
                                  event.stopPropagation();
                                  if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submitEdit(); }
                                  if (event.key === "Escape")                   { event.preventDefault(); setIsEditing(false); }
                              }}
                              className="w-full bg-white dark:bg-slate-950 border border-indigo-400 dark:border-indigo-500 rounded-xl px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-indigo-500" />
                    <div className="flex items-center justify-end gap-2">
                        <span className="mr-auto text-[11px] text-amber-600 dark:text-amber-400">이 질문 이후의 대화는 삭제됩니다</span>
                        <button onClick={() => setIsEditing(false)}
                                className="px-3 py-1.5 rounded-lg text-[11px] font-medium bg-slate-200 hover:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700 transition">취소</button>
                        <button onClick={submitEdit}
                                className="px-3 py-1.5 rounded-lg text-[11px] font-medium bg-indigo-600 hover:bg-indigo-500 text-white transition">여기서부터 다시 보내기</button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="group flex justify-end items-center gap-1.5">
            <button onClick={startEdit} title="질문 수정 후 여기서부터 다시 대화" aria-label="질문 수정"
                    className="shrink-0 w-6 h-6 rounded-lg flex items-center justify-center text-slate-400 dark:text-slate-500 hover:text-indigo-500 dark:hover:text-indigo-400 hover:bg-slate-200 dark:hover:bg-slate-800 opacity-0 group-hover:opacity-100 transition text-xs">
                ✎
            </button>
            <div className="max-w-[78%] md:max-w-[65%] bg-slate-200 dark:bg-slate-700 text-slate-900 dark:text-slate-100 rounded-2xl rounded-br-md px-4 py-2.5 text-sm leading-relaxed shadow">
                {/* 함께 보낸 이미지 : 새 탭으로 원본을 열 수 있게 링크로 감싼다 */}
                {(imageUrlList || []).length > 0 ? (
                    <div className="mb-1.5 flex flex-wrap gap-1.5">
                        {imageUrlList.map(imageUrl => (
                            <a key={imageUrl} href={imageUrl} target="_blank" rel="noopener noreferrer"
                               className="block w-20 h-20 rounded-lg overflow-hidden border border-slate-300 dark:border-slate-600 bg-slate-100 dark:bg-slate-800">
                                <img src={imageUrl} alt="첨부 이미지" loading="lazy" className="w-full h-full object-cover" />
                            </a>
                        ))}
                    </div>
                ) : null}

                {/* 통째로 참조한 답변 : 어떤 답변을 함께 보냈는지 번호로 되짚어 준다 */}
                {(referencedAgentIndexList || []).length > 0 ? (
                    <p className="mb-1.5 flex flex-wrap gap-1">
                        {referencedAgentIndexList.map(agentIndex => (
                            <span key={agentIndex}
                                  className="px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-950/50 text-amber-800 dark:text-amber-300 text-[10px] font-medium">
                                📌 답변 #{agentIndex + 1}
                            </span>
                        ))}
                    </p>
                ) : null}

                {/* 참조 발췌 : 질문과 함께 모델에 전달된 내용을 인용 블록으로 되짚어 준다 */}
                {referencedText ? (
                    <p className="mb-1.5 pl-2 border-l-2 border-indigo-400 dark:border-indigo-500 text-[11px] leading-relaxed text-slate-600 dark:text-slate-300 whitespace-pre-wrap break-words line-clamp-4">
                        ❝ {referencedText}
                    </p>
                ) : null}
                <span className="whitespace-pre-wrap">{text}</span>
            </div>
        </div>
    );
}
