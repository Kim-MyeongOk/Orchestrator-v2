import { stripMarkdownForPreview } from "../utils/markdown";
import { formatRelativeTime }      from "../utils/time";
import { useTimeTick }             from "../utils/time";

/* 사이드바 「북마크」 탭 : 저장한 답변 목록.
   항목을 누르면 원본 채팅방으로 전환하고 해당 답변 위치로 스크롤·강조한다. */

export default function BookmarkList({ bookmarkList, roomList, onOpenBookmark, onRemoveBookmark }) {
    useTimeTick();   // 30초마다 상대 시간 갱신

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

                return (
                    <div key={bookmark.bookmarkId} onClick={() => onOpenBookmark(bookmark)}
                         className="group px-3 py-2 rounded-lg cursor-pointer transition border border-transparent text-slate-600 dark:text-slate-400 hover:bg-slate-200/70 dark:hover:bg-slate-800/60 hover:border-slate-300 dark:hover:border-slate-700">
                        {/* 미리보기 : 마크다운 기호를 걷어낸 첫 두 줄 정도만 노출한다 */}
                        <p className="text-[11px] leading-relaxed text-slate-700 dark:text-slate-300 line-clamp-2">
                            {stripMarkdownForPreview(bookmark.text)}
                        </p>
                        <div className="flex items-center gap-1.5 mt-1">
                            <span className="flex-1 min-w-0 truncate text-[10px] text-indigo-500 dark:text-indigo-400">{roomTitle}</span>
                            <span className="shrink-0 text-[10px] text-slate-400 dark:text-slate-600 font-mono">{formatRelativeTime(bookmark.completedAt)}</span>
                            <button title="북마크 삭제" aria-label="북마크 삭제"
                                    onClick={(event) => { event.stopPropagation(); onRemoveBookmark(bookmark); }}
                                    className="shrink-0 w-4 h-4 rounded flex items-center justify-center text-slate-400 dark:text-slate-600 hover:text-red-500 dark:hover:text-red-400 opacity-0 group-hover:opacity-100 transition text-[10px]">
                                ✕
                            </button>
                        </div>
                    </div>
                );
            })}
        </nav>
    );
}
