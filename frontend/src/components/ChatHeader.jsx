import { MoonIcon } from "./icons";
import { SunIcon }  from "./icons";

/* 상단 바 : 현재 방 제목 · Thread ID · 모델 배지 · 응답 상태 · 테마 토글 */

export default function ChatHeader({ room, statusText, statusToneClass, isDarkTheme, onToggleTheme }) {
    const threadIdText = room ? `${room.threadId.slice(0, 13)}…` : "—";

    return (
        <header className="shrink-0 h-14 px-4 md:px-6 bg-white/70 dark:bg-slate-900/60 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between backdrop-blur">
            <div className="flex items-center gap-2 min-w-0">
                <span className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate max-w-[180px]">
                    {room ? room.title : "—"}
                </span>
                <span className="text-slate-300 dark:text-slate-700">·</span>
                <code className="text-[11px] text-slate-500 font-mono truncate">{threadIdText}</code>
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-200 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-400 shrink-0">
                    {room?.model || "기본 모델"}
                </span>
            </div>

            <div className="flex items-center gap-2.5 shrink-0">
                <span className={`w-2 h-2 rounded-full ${statusToneClass}`} />
                <span className="text-[11px] text-slate-500 dark:text-slate-400">{statusText}</span>
                <button onClick={onToggleTheme} title="테마 전환" aria-label="테마 전환"
                        className="w-8 h-8 rounded-lg flex items-center justify-center text-amber-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800 transition">
                    {isDarkTheme ? <MoonIcon /> : <SunIcon />}
                </button>
            </div>
        </header>
    );
}
