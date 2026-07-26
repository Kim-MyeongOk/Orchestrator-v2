import { useEffect } from "react";
import { useRef }    from "react";
import { useState }  from "react";

import { stripMarkdownForPreview } from "../utils/markdown";
import { formatRelativeTime }      from "../utils/time";
import { useTimeTick }             from "../utils/time";

/* 사이드바 「북마크」 탭 : 저장한 답변 목록.
   항목을 누르면 원본 채팅방으로 전환하고 해당 답변 위치로 스크롤·강조한다.
   메모는 인라인 입력창으로 편집한다 — 사이드바가 좁아 모달을 띄우면 목록 맥락이 가려지기 때문이다. */

const MEMO_MAXIMUM_LENGTH = 1000;   // 서버(ServerApplication.BOOKMARK_MEMO_MAXIMUM_LENGTH)와 맞춘 값

export default function BookmarkList({ bookmarkList, roomList, onOpenBookmark, onRemoveBookmark, onUpdateBookmarkMemo }) {
    useTimeTick();   // 30초마다 상대 시간 갱신

    const [editingBookmarkId, setEditingBookmarkId] = useState(null);
    const [editingMemoText, setEditingMemoText]     = useState("");
    const [isSaving, setIsSaving]                   = useState(false);

    const textAreaRef = useRef(null);

    useEffect(() => {
        // 편집 시작 시 입력창으로 포커스를 옮기고 커서를 맨 뒤에 둔다
        if (!editingBookmarkId || !textAreaRef.current) return;
        textAreaRef.current.focus();
        textAreaRef.current.setSelectionRange(textAreaRef.current.value.length, textAreaRef.current.value.length);
    }, [editingBookmarkId]);

    function startEditing(event, bookmark) {
        event.stopPropagation();   // 항목 클릭(=방 이동)으로 번지지 않게 한다
        setEditingBookmarkId(bookmark.bookmarkId);
        setEditingMemoText(bookmark.memo || "");
    }

    function cancelEditing() {
        setEditingBookmarkId(null);
        setEditingMemoText("");
    }

    async function saveEditing(bookmarkId) {
        if (isSaving) return;
        setIsSaving(true);
        const isSaved = await onUpdateBookmarkMemo(bookmarkId, editingMemoText);
        setIsSaving(false);
        // 저장 실패 시에는 입력창을 열어 둔다 (사용자가 쓴 내용을 잃지 않도록)
        if (isSaved) cancelEditing();
    }

    function onMemoKeyDown(event, bookmarkId) {
        // Enter : 저장 / Shift+Enter : 줄바꿈 / Escape : 취소
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            saveEditing(bookmarkId);
            return;
        }
        if (event.key === "Escape") {
            event.preventDefault();
            cancelEditing();
        }
    }

    if (bookmarkList.length === 0) {
        return (
            <nav className="chat-scroll flex-1 overflow-y-auto px-3 space-y-1.5 min-h-0">
                <p className="text-center text-[11px] text-slate-400 dark:text-slate-600 pt-8 leading-relaxed">
                    북마크한 답변이 없습니다.<br />답변 하단의 북마크 아이콘을 눌러 저장하세요.
                </p>
            </nav>
        );
    }

    return (
        <nav className="chat-scroll flex-1 overflow-y-auto px-3 space-y-1.5 min-h-0">
            {bookmarkList.map(bookmark => {
                const room      = roomList.find(roomEntry => roomEntry.roomId === bookmark.roomId);
                const roomTitle = room ? room.title : "(삭제된 채팅방)";
                const isEditing = editingBookmarkId === bookmark.bookmarkId;

                return (
                    <div key={bookmark.bookmarkId} onClick={() => { if (!isEditing) onOpenBookmark(bookmark); }}
                         className="group px-3 py-2 rounded-lg cursor-pointer transition border border-transparent text-slate-600 dark:text-slate-400 hover:bg-slate-200/70 dark:hover:bg-slate-800/60 hover:border-slate-300 dark:hover:border-slate-700">
                        {/* 미리보기 : 마크다운 기호를 걷어낸 첫 두 줄 정도만 노출한다 */}
                        <p className="text-[11px] leading-relaxed text-slate-700 dark:text-slate-300 line-clamp-2">
                            {stripMarkdownForPreview(bookmark.text)}
                        </p>

                        {/* 메모 : 저장된 값이 있을 때만 보여준다 (편집 중에는 입력창이 대신한다) */}
                        {!isEditing && bookmark.memo ? (
                            <p className="mt-1 pl-2 border-l-2 border-amber-400/70 dark:border-amber-500/60 text-[10px] leading-relaxed text-amber-700 dark:text-amber-300 whitespace-pre-wrap break-words line-clamp-3">
                                {bookmark.memo}
                            </p>
                        ) : null}

                        {isEditing ? (
                            <div className="mt-1.5" onClick={(event) => event.stopPropagation()}>
                                <textarea ref={textAreaRef} rows={3} value={editingMemoText} maxLength={MEMO_MAXIMUM_LENGTH}
                                          onChange={(event) => setEditingMemoText(event.target.value)}
                                          onKeyDown={(event) => onMemoKeyDown(event, bookmark.bookmarkId)}
                                          placeholder="메모를 입력하세요 (Enter 저장 · Shift+Enter 줄바꿈 · Esc 취소)"
                                          className="w-full resize-none bg-white dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg px-2 py-1.5 text-[11px] leading-relaxed text-slate-700 dark:text-slate-200 placeholder:text-slate-400 dark:placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 transition" />
                                <div className="flex items-center gap-1.5 mt-1">
                                    <span className="flex-1 text-[10px] text-slate-400 dark:text-slate-600 font-mono">{editingMemoText.length}/{MEMO_MAXIMUM_LENGTH}</span>
                                    <button onClick={cancelEditing} disabled={isSaving}
                                            className="px-2 py-1 rounded-md text-[10px] font-medium bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-300 dark:hover:bg-slate-700 disabled:opacity-50 transition">
                                        취소
                                    </button>
                                    <button onClick={() => saveEditing(bookmark.bookmarkId)} disabled={isSaving}
                                            className="px-2 py-1 rounded-md text-[10px] font-semibold bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-50 transition">
                                        {isSaving ? "저장 중…" : "저장"}
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <div className="flex items-center gap-1.5 mt-1">
                                <span className="flex-1 min-w-0 truncate text-[10px] text-indigo-500 dark:text-indigo-400">{roomTitle}</span>
                                <span className="shrink-0 text-[10px] text-slate-400 dark:text-slate-600 font-mono">{formatRelativeTime(bookmark.completedAt)}</span>
                                <button title={bookmark.memo ? "메모 수정" : "메모 추가"} aria-label={bookmark.memo ? "메모 수정" : "메모 추가"}
                                        onClick={(event) => startEditing(event, bookmark)}
                                        className="shrink-0 w-4 h-4 rounded flex items-center justify-center text-slate-400 dark:text-slate-600 hover:text-amber-500 dark:hover:text-amber-400 opacity-0 group-hover:opacity-100 transition text-[10px]">
                                    ✎
                                </button>
                                <button title="북마크 삭제" aria-label="북마크 삭제"
                                        onClick={(event) => { event.stopPropagation(); onRemoveBookmark(bookmark); }}
                                        className="shrink-0 w-4 h-4 rounded flex items-center justify-center text-slate-400 dark:text-slate-600 hover:text-red-500 dark:hover:text-red-400 opacity-0 group-hover:opacity-100 transition text-[10px]">
                                    ✕
                                </button>
                            </div>
                        )}
                    </div>
                );
            })}
        </nav>
    );
}
