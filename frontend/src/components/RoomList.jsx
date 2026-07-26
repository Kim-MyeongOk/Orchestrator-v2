import { useEffect } from "react";
import { useRef }    from "react";
import { useState }  from "react";

/* 사이드바 「채팅방」 탭 : 방 목록 + 인라인 이름 편집 + 삭제.
   응답 중인 방은 전환·이름 변경이 막힌다 (응답이 다른 방에 섞이는 것을 방지). */

export default function RoomList({ roomList, activeRoomId, isStreaming, onSwitchRoom, onRenameRoom, onDeleteRoom, onBlockedRename }) {
    const [renamingRoomId, setRenamingRoomId] = useState(null);
    const [draftTitle, setDraftTitle]         = useState("");
    const titleInputRef                       = useRef(null);

    useEffect(() => {
        if (renamingRoomId === null) return;
        titleInputRef.current?.focus();
        titleInputRef.current?.select();
    }, [renamingRoomId]);

    const startRename = (event, room) => {
        event.stopPropagation();
        if (isStreaming && room.roomId === activeRoomId) { onBlockedRename(); return; }
        setDraftTitle(room.title);
        setRenamingRoomId(room.roomId);
    };

    const commitRename = (roomId) => {
        setRenamingRoomId(null);
        onRenameRoom(roomId, draftTitle);
    };

    return (
        <nav className="chat-scroll flex-1 overflow-y-auto px-3 space-y-1 min-h-0">
            {roomList.map(room => {
                const isActive = room.roomId === activeRoomId;

                // 이름 편집 중인 방 : 입력창만 표시하고 방 전환 클릭은 비활성화한다
                if (room.roomId === renamingRoomId) {
                    return (
                        <div key={room.roomId}
                             className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs bg-slate-200 dark:bg-slate-800 border border-slate-300 dark:border-slate-700">
                            <input ref={titleInputRef} type="text" value={draftTitle} maxLength={60}
                                   onChange={(event) => setDraftTitle(event.target.value)}
                                   onClick={(event) => event.stopPropagation()}
                                   onBlur={() => commitRename(room.roomId)}
                                   onKeyDown={(event) => {
                                       event.stopPropagation();   // Enter 가 메시지 전송으로 번지지 않게 한다
                                       if (event.key === "Enter")  { event.preventDefault(); commitRename(room.roomId); }
                                       if (event.key === "Escape") { event.preventDefault(); setRenamingRoomId(null); }
                                   }}
                                   className="flex-1 min-w-0 bg-white dark:bg-slate-950 border border-indigo-400 dark:border-indigo-500 rounded px-1.5 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500" />
                        </div>
                    );
                }

                const isRenameBlocked = isStreaming && isActive;

                return (
                    <div key={room.roomId} onClick={() => onSwitchRoom(room.roomId)}
                         className={`group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition text-xs ${
                             isActive
                                 ? "bg-slate-200 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100"
                                 : "text-slate-600 dark:text-slate-400 hover:bg-slate-200/70 dark:hover:bg-slate-800/60 border border-transparent"}`}>
                        <span className="flex-1 truncate" title="더블클릭하면 이름을 변경할 수 있습니다"
                              onDoubleClick={(event) => startRename(event, room)}>
                            {room.title}
                        </span>
                        <span className="text-[9px] text-slate-400 dark:text-slate-600 shrink-0">
                            {room.model ? room.model.split(":")[0] : ""}
                        </span>
                        <button onClick={(event) => startRename(event, room)}
                                title={isRenameBlocked ? "응답 중에는 이름을 변경할 수 없습니다" : "채팅방 이름 변경"}
                                className={`shrink-0 w-5 h-5 rounded flex items-center justify-center transition opacity-0 group-hover:opacity-100 ${
                                    isRenameBlocked
                                        ? "text-slate-300 dark:text-slate-700 cursor-not-allowed"
                                        : "text-slate-400 dark:text-slate-600 hover:text-indigo-500 dark:hover:text-indigo-400 hover:bg-slate-300/60 dark:hover:bg-slate-700/60"}`}>
                            ✎
                        </button>
                        <button onClick={(event) => { event.stopPropagation(); onDeleteRoom(room.roomId); }}
                                title="채팅방 삭제" aria-label="채팅방 삭제"
                                className="shrink-0 w-5 h-5 rounded flex items-center justify-center text-slate-400 dark:text-slate-600 hover:text-red-500 dark:hover:text-red-400 hover:bg-slate-300/60 dark:hover:bg-slate-700/60 opacity-0 group-hover:opacity-100 transition">
                            ✕
                        </button>
                    </div>
                );
            })}
        </nav>
    );
}
