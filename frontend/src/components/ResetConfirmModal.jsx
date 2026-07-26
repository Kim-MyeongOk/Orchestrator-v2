import { useEffect } from "react";

/* 세션 초기화 확인 모달 : 실수로 대화가 날아가는 것을 방지한다 (ESC / 배경 클릭으로 닫힘) */

export default function ResetConfirmModal({ isOpen, onCancel, onConfirm }) {
    useEffect(() => {
        if (!isOpen) return;
        const onKeyDown = (event) => { if (event.key === "Escape") onCancel(); };
        document.addEventListener("keydown", onKeyDown);
        return () => document.removeEventListener("keydown", onKeyDown);
    }, [isOpen, onCancel]);

    if (!isOpen) return null;

    return (
        <div onClick={(event) => { if (event.target === event.currentTarget) onCancel(); }}
             className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 dark:bg-black/60 backdrop-blur-sm">
            <div className="w-80 mx-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 shadow-2xl p-5 bubble-enter">
                <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">현재 세션을 초기화할까요?</h2>
                <p className="mt-2 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
                    이 방의 대화 내용이 모두 지워지고 새 Thread 가 발급됩니다. 이전 체크포인트 대화는 더 이상 이어지지 않습니다.
                </p>
                <div className="mt-4 flex gap-2 justify-end">
                    <button onClick={onCancel}
                            className="px-3.5 py-2 rounded-lg text-xs font-medium bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 transition">
                        취소
                    </button>
                    <button onClick={onConfirm}
                            className="px-3.5 py-2 rounded-lg text-xs font-semibold bg-red-600 hover:bg-red-500 text-white transition">
                        초기화
                    </button>
                </div>
            </div>
        </div>
    );
}
