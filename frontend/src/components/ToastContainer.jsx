/* 우측 하단 토스트 알림 : 서버 연결 실패 등 비차단 오류를 알린다 */

export default function ToastContainer({ toastList, onDismiss }) {
    return (
        <div className="fixed bottom-5 right-5 z-50 space-y-2 w-80 max-w-[90vw]">
            {toastList.map(toast => (
                <div key={toast.toastId} onClick={() => onDismiss(toast.toastId)}
                     className={`toast-enter ${toast.toneClass} text-white text-xs leading-relaxed rounded-lg px-4 py-3 shadow-xl cursor-pointer whitespace-pre-wrap`}>
                    {toast.text}
                </div>
            ))}
        </div>
    );
}
