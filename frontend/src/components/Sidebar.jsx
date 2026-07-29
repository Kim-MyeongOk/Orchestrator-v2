import BookmarkList from "./BookmarkList";
import RoomList     from "./RoomList";

import { getApiUrl } from "../api/chatApi";

const TAB_BUTTON_BASE_CLASS   = "flex-1 py-1.5 rounded-md text-[11px] font-semibold transition";
const TAB_ACTIVE_CLASS        = "bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm";
const TAB_INACTIVE_CLASS      = "text-slate-500 dark:text-slate-400";
const SELECT_CLASS            = "w-full bg-white dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg px-2.5 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 transition";
const FIELD_LABEL_CLASS       = "block text-[11px] font-medium text-slate-500 dark:text-slate-400 mb-1.5";

/* 좌측 사이드바 : 새 채팅방 · 채팅방/북마크 탭 · 세션 설정(모델·개발자 모드)
   생각 정도는 입력창 톱니바퀴(ReasoningEffortPopover)에 있다 */

export default function Sidebar({
    userId, roomList, activeRoom, activeRoomId, isStreaming,
    sidebarTabName, onSidebarTabChange,
    bookmarkList, onOpenBookmark, onRemoveBookmark, onUpdateBookmarkMemo,
    onCreateRoom, onSwitchRoom, onRenameRoom, onDeleteRoom, onBlockedRename,
    modelNameList, defaultModelName, onModelChange,
    isDeveloperMode, onToggleDeveloperMode, apiUrlText, onApiUrlChange,
    onResetSession, onLogout
}) {
    return (
        <aside className="md:w-72 shrink-0 bg-white/80 dark:bg-slate-900/80 border-b md:border-b-0 md:border-r border-slate-200 dark:border-slate-800 flex flex-col max-h-64 md:max-h-none overflow-y-auto md:overflow-hidden">

            <div className="p-4 md:p-5 pb-3 space-y-4">
                <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-sm font-bold text-white shadow-lg shadow-indigo-300 dark:shadow-indigo-950">O</div>
                    <div className="flex-1 min-w-0">
                        <h1 className="text-sm font-semibold tracking-tight">Orchestrator Chat</h1>
                        <p className="text-[11px] text-slate-500">LangGraph 체크포인트 대화</p>
                    </div>
                </div>

                <button onClick={onCreateRoom}
                        className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold transition shadow-lg shadow-indigo-200 dark:shadow-indigo-950/40">
                    ＋ 새 채팅방
                </button>
            </div>

            {/* 사이드바 탭 : 채팅방 / 북마크 */}
            <div className="px-3 pb-2">
                <div className="flex gap-1 p-1 rounded-lg bg-slate-200/70 dark:bg-slate-800/60">
                    <button onClick={() => onSidebarTabChange("rooms")}
                            className={`${TAB_BUTTON_BASE_CLASS} ${sidebarTabName === "rooms" ? TAB_ACTIVE_CLASS : TAB_INACTIVE_CLASS}`}>채팅방</button>
                    <button onClick={() => onSidebarTabChange("bookmarks")}
                            className={`${TAB_BUTTON_BASE_CLASS} ${sidebarTabName === "bookmarks" ? TAB_ACTIVE_CLASS : TAB_INACTIVE_CLASS}`}>북마크</button>
                </div>
            </div>

            <div className="flex-1 min-h-0 flex flex-col">
                {sidebarTabName === "rooms"
                    ? <RoomList roomList={roomList} activeRoomId={activeRoomId} isStreaming={isStreaming}
                                onSwitchRoom={onSwitchRoom} onRenameRoom={onRenameRoom}
                                onDeleteRoom={onDeleteRoom} onBlockedRename={onBlockedRename} />
                    : <BookmarkList bookmarkList={bookmarkList} roomList={roomList}
                                    onOpenBookmark={onOpenBookmark} onRemoveBookmark={onRemoveBookmark}
                                    onUpdateBookmarkMemo={onUpdateBookmarkMemo} />}
            </div>

            {/* 세션 설정 */}
            <div className="p-4 md:p-5 pt-3 space-y-3 border-t border-slate-200 dark:border-slate-800/70">
                <div>
                    <label className={FIELD_LABEL_CLASS}>
                        로그인 사용자 <span className="text-slate-400 dark:text-slate-600">(이 ID 로만 채팅·방 저장)</span>
                    </label>
                    <div className="flex gap-1.5">
                        <input type="text" value={userId} readOnly
                               className="flex-1 min-w-0 bg-slate-100 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-slate-600 dark:text-slate-300 focus:outline-none" />
                        <button onClick={onLogout} title="로그아웃"
                                className="shrink-0 px-2.5 rounded-lg bg-slate-200 dark:bg-slate-800 hover:bg-red-100 dark:hover:bg-red-950/60 text-slate-500 hover:text-red-600 dark:hover:text-red-400 border border-slate-300 dark:border-slate-700 text-xs transition">
                            로그아웃
                        </button>
                    </div>
                </div>

                <div>
                    <label className={FIELD_LABEL_CLASS}>모델</label>
                    <select value={activeRoom?.model || ""} onChange={(event) => onModelChange(event.target.value)} className={SELECT_CLASS}>
                        <option value="">{defaultModelName ? `(기본 : ${defaultModelName})` : "(기본 모델)"}</option>
                        {modelNameList.map(modelName => <option key={modelName} value={modelName}>{modelName}</option>)}
                    </select>
                </div>

                {/* 생각 정도는 입력창의 톱니바퀴(ReasoningEffortPopover)로 옮겼다 —
                    3단계 선택이 두 군데 있으면 어느 쪽이 듣는지 헷갈린다 */}

                {/* 개발자 모드 토글 : 켰을 때만 API URL / Thread ID 노출 */}
                <div className="flex items-center justify-between">
                    <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 select-none">개발자 모드</span>
                    <button onClick={onToggleDeveloperMode} role="switch" aria-checked={isDeveloperMode} aria-label="개발자 모드"
                            className={`relative w-9 h-5 rounded-full transition-colors ${isDeveloperMode ? "bg-indigo-600" : "bg-slate-300 dark:bg-slate-700"}`}>
                        <span className="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform"
                              style={{ transform : isDeveloperMode ? "translateX(16px)" : "translateX(0)" }} />
                    </button>
                </div>

                {isDeveloperMode ? (
                    <div className="space-y-3">
                        <div>
                            <label className={FIELD_LABEL_CLASS}>백엔드 API URL</label>
                            <input type="text" value={apiUrlText} onChange={(event) => onApiUrlChange(event.target.value)}
                                   className="w-full bg-white dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 transition" />
                        </div>
                        <div>
                            <label className={FIELD_LABEL_CLASS}>
                                Thread ID <span className="text-slate-400 dark:text-slate-600">(현재 방)</span>
                            </label>
                            <input type="text" value={activeRoom?.threadId || ""} readOnly
                                   className="w-full bg-slate-100 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-2 text-[11px] font-mono text-slate-500 focus:outline-none" />
                        </div>
                        <a href={`${getApiUrl()}/dev/api-client`} target="_blank" rel="noreferrer"
                           className="block text-center px-2 py-1.5 rounded-lg text-[11px] font-medium bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-950/60 dark:hover:bg-indigo-900/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800 transition">
                            API 테스트 ↗
                        </a>
                    </div>
                ) : null}

                <button onClick={onResetSession}
                        className="w-full py-2 bg-slate-200 hover:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700 border border-slate-300 dark:border-slate-700 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-300 transition">
                    현재 세션 초기화
                </button>
            </div>
        </aside>
    );
}
