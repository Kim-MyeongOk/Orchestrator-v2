import { useCallback } from "react";
import { useEffect }   from "react";
import { useState }    from "react";

import ChatHeader        from "./components/ChatHeader";
import ChatInput         from "./components/ChatInput";
import ChatMessageList   from "./components/ChatMessageList";
import ResetConfirmModal from "./components/ResetConfirmModal";
import Sidebar           from "./components/Sidebar";
import ToastContainer    from "./components/ToastContainer";

import { useBookmarks }  from "./hooks/useBookmarks";
import { useChatStream } from "./hooks/useChatStream";
import { useRooms }      from "./hooks/useRooms";
import { useTheme }      from "./hooks/useTheme";
import { useToast }      from "./hooks/useToast";
import { useTTS }        from "./hooks/useTTS";

import { getApiUrl }          from "./api/chatApi";
import { getUserId }          from "./api/chatApi";
import { listModelsAsync }    from "./api/chatApi";
import { logout }             from "./api/chatApi";
import { setApiUrl }          from "./api/chatApi";
import { truncateThreadAsync } from "./api/chatApi";

import { DEVELOPER_MODE_STORAGE_KEY } from "./constants/storageKeys";

const IDLE_STATUS      = { text : "대기",   toneClass : "bg-slate-400 dark:bg-slate-600" };
const STREAMING_STATUS = { text : "응답 중", toneClass : "bg-emerald-400 animate-pulse" };

export default function App() {
    const { isDarkTheme, toggleTheme }            = useTheme();
    const { toastList, showToast, dismissToast }  = useToast();

    const [inputValue, setInputValue]                     = useState("");
    const [referencedText, setReferencedText]             = useState("");   // 답변에서 「참조하기」로 담은 발췌 (전송 후 비운다)
    const [sidebarTabName, setSidebarTabName]             = useState("rooms");
    const [isResetModalOpen, setIsResetModalOpen]         = useState(false);
    const [scrollTargetAgentIndex, setScrollTargetAgentIndex] = useState(null);
    const [statusInfo, setStatusInfo]                     = useState(IDLE_STATUS);
    const [apiUrlText, setApiUrlText]                     = useState(getApiUrl());
    const [modelNameList, setModelNameList]               = useState([]);
    const [defaultModelName, setDefaultModelName]         = useState("");
    const [isDeveloperMode, setIsDeveloperMode]           = useState(
        () => localStorage.getItem(DEVELOPER_MODE_STORAGE_KEY) === "on"
    );

    const rooms     = useRooms({ showToast });
    const bookmarks = useBookmarks({ showToast });
    // speechSynthesis 는 창 전체에 하나뿐이라 훅도 여기서 한 번만 만든다 (말풍선마다 두면 재생 상태가 어긋난다)
    const tts       = useTTS();

    const stream = useChatStream({
        appendMessage          : rooms.appendMessage,
        applyFirstMessageTitle : rooms.applyFirstMessageTitle,
        setRoomLastRunId       : rooms.setRoomLastRunId,
        showToast              : showToast,
        isDeveloperMode        : isDeveloperMode
    });

    const { activeRoom }  = rooms;
    const { isStreaming } = stream;

    useEffect(() => { setStatusInfo(isStreaming ? STREAMING_STATUS : IDLE_STATUS); }, [isStreaming]);

    /* ── 모델 목록 : 백엔드보다 페이지를 먼저 연 경우를 위해 지수 백오프로 재시도한다 ── */

    useEffect(() => {
        let isCancelled  = false;
        let retryTimerId = null;

        const loadModelOptionsAsync = async (attemptCount = 0) => {
            try {
                const { defaultModel, modelNameList : loadedModelNameList } = await listModelsAsync();
                if (isCancelled) return;
                setDefaultModelName(defaultModel);
                setModelNameList(loadedModelNameList);
                // 백엔드 프로바이더가 바뀌면 방에 저장된 이전 모델이 무효가 된다 → 기본 모델로 자동 초기화
                rooms.dropInvalidRoomModels(new Set(loadedModelNameList));
            } catch (error) {
                if (isCancelled) return;
                if (attemptCount < 3) {
                    retryTimerId = setTimeout(() => loadModelOptionsAsync(attemptCount + 1), 1000 * 2 ** attemptCount);   // 1초 → 2초 → 4초
                    return;
                }
                showToast(`⚠ 모델 목록 로드 실패 (${error.message})\n기본 모델로 동작합니다. 백엔드 확인 후 새로고침하세요.`);
            }
        };
        loadModelOptionsAsync();

        return () => { isCancelled = true; if (retryTimerId !== null) clearTimeout(retryTimerId); };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [apiUrlText]);

    /* ── 개발자 모드 ── */

    const onToggleDeveloperMode = useCallback(() => {
        setIsDeveloperMode(previousIsEnabled => {
            const nextIsEnabled = !previousIsEnabled;
            localStorage.setItem(DEVELOPER_MODE_STORAGE_KEY, nextIsEnabled ? "on" : "off");
            return nextIsEnabled;
        });
    }, []);

    const onApiUrlChange = useCallback((newApiUrlText) => {
        setApiUrlText(newApiUrlText);
        setApiUrl(newApiUrlText);
    }, []);

    /* ── 전송 ── */

    const onSend = useCallback(async () => {
        const messageText = inputValue.trim();
        if (!messageText || isStreaming || !activeRoom) return;
        const sentReferencedText = referencedText;
        setInputValue("");
        setReferencedText("");   // 참조는 한 턴만 따라간다 (다음 질문에 의도치 않게 달라붙지 않도록)
        const finalStatus = await stream.sendMessageAsync(activeRoom, messageText, sentReferencedText);
        setStatusInfo(finalStatus);
    }, [activeRoom, inputValue, isStreaming, referencedText, stream]);

    const onRetryError = useCallback(async (errorMessage) => {
        if (isStreaming || !activeRoom) return;
        rooms.removeErrorMessage(activeRoom.roomId, errorMessage.text);
        // 실패한 턴에 붙어 있던 참조를 그대로 다시 실어 보낸다
        const finalStatus = await stream.executeStreamTurnAsync(activeRoom, errorMessage.retryMessageText, errorMessage.retryReferencedText || "");
        setStatusInfo(finalStatus);
    }, [activeRoom, isStreaming, rooms, stream]);

    /* ── 참조하기 : 답변에서 드래그한 구간을 다음 질문의 문맥으로 담아 둔다 ── */

    const onQuoteText = useCallback((selectedText) => {
        if (isStreaming) { showToast("⚠ 응답 중에는 참조를 담을 수 없습니다."); return; }
        setReferencedText(selectedText);
    }, [isStreaming, showToast]);

    /* ── 질문 수정 : 체크포인트를 절단하고 그 지점부터 다시 이어간다 ── */

    const onSubmitEdit = useCallback(async (userMessageIndex, editedText) => {
        if (!activeRoom || isStreaming || !editedText) return;

        // ① 서버 체크포인트에서 이 질문 이후를 제거한다 (모델이 삭제된 대화를 기억하지 않도록)
        try {
            await truncateThreadAsync(activeRoom.threadId, userMessageIndex);
        } catch (error) {
            showToast(`⚠ 이전 대화 정리에 실패했습니다 : ${error.message}\n서버 상태를 확인해주세요.`);
            return;
        }

        // ② 화면·저장 목록에서도 해당 질문 이후를 잘라낸다
        const storedMessageList = activeRoom.messages || [];
        let   userMessageSeenCount = 0;
        let   cutIndex             = storedMessageList.length;
        for (let messageIndex = 0; messageIndex < storedMessageList.length; messageIndex += 1) {
            if (storedMessageList[messageIndex].role !== "user") continue;
            if (userMessageSeenCount === userMessageIndex) { cutIndex = messageIndex; break; }
            userMessageSeenCount += 1;
        }

        // 잘려나갈 답변들의 북마크를 먼저 정리한다 (남겨둘 답변 수 = 절단 지점까지의 agent 메시지 수)
        const keptMessageList     = storedMessageList.slice(0, cutIndex);
        const keptAgentMessageCount = keptMessageList.filter(storedMessage => storedMessage.role === "agent").length;
        bookmarks.removeBookmarksFromAgentIndex(activeRoom.roomId, keptAgentMessageCount);
        rooms.replaceMessages(activeRoom.roomId, keptMessageList);

        // ③ 수정된 질문으로 그 지점부터 대화를 이어간다
        const finalStatus = await stream.sendMessageAsync({ ...activeRoom, messages : keptMessageList }, editedText);
        setStatusInfo(finalStatus);
    }, [activeRoom, bookmarks, isStreaming, rooms, showToast, stream]);

    /* ── 방 조작 ── */

    const onSwitchRoom = useCallback((roomId) => {
        if (isStreaming) { showToast("⚠ 응답 중에는 다른 대화로 이동할 수 없습니다."); return; }
        tts.stopSpeaking();   // 떠난 방의 답변을 계속 읽으면 정지 버튼이 화면에 없어 멈출 방법이 없다
        setReferencedText("");   // 참조는 떠나온 방의 답변에서 딴 것이라 여기로 들고 오지 않는다
        setScrollTargetAgentIndex(null);
        rooms.switchRoom(roomId);
    }, [isStreaming, rooms, showToast, tts]);

    const onDeleteRoom = useCallback((roomId) => {
        if (isStreaming) return;
        bookmarks.removeRoomBookmarks(roomId);   // 삭제된 방의 북마크도 함께 정리
        rooms.deleteRoom(roomId);
    }, [bookmarks, isStreaming, rooms]);

    const onConfirmReset = useCallback(() => {
        setIsResetModalOpen(false);
        if (!activeRoom) return;
        bookmarks.removeRoomBookmarks(activeRoom.roomId);
        rooms.resetActiveSession();
        showToast("새 세션이 시작되었습니다. 이전 체크포인트와 분리된 새 Thread 입니다.", "bg-slate-700/95");
    }, [activeRoom, bookmarks, rooms, showToast]);

    /* ── 북마크 이동 : 해당 방으로 전환 후 답변 위치로 스크롤·강조 ── */

    const onOpenBookmark = useCallback((bookmark) => {
        if (isStreaming) { showToast("⚠ 응답 중에는 다른 대화로 이동할 수 없습니다."); return; }
        if (!rooms.roomList.some(room => room.roomId === bookmark.roomId)) {
            showToast("⚠ 원본 채팅방이 삭제되어 이동할 수 없습니다.");
            return;
        }
        if (bookmark.roomId !== rooms.activeRoomId) rooms.switchRoom(bookmark.roomId);
        // 같은 값을 다시 눌러도 스크롤되도록 null 을 거쳐 새 값을 넣는다
        setScrollTargetAgentIndex(null);
        requestAnimationFrame(() => setScrollTargetAgentIndex(bookmark.agentIndex));
    }, [isStreaming, rooms, showToast]);

    return (
        <div className="h-full flex flex-col md:flex-row">
            <Sidebar
                userId={getUserId()}
                roomList={rooms.roomList}
                activeRoom={activeRoom}
                activeRoomId={rooms.activeRoomId}
                isStreaming={isStreaming}
                sidebarTabName={sidebarTabName}
                onSidebarTabChange={setSidebarTabName}
                bookmarkList={bookmarks.bookmarkList}
                onOpenBookmark={onOpenBookmark}
                onRemoveBookmark={(bookmark) => bookmarks.toggleBookmark(bookmark.roomId, bookmark.agentIndex, bookmark.text, bookmark.completedAt)}
                onUpdateBookmarkMemo={bookmarks.updateBookmarkMemo}
                onCreateRoom={rooms.createRoom}
                onSwitchRoom={onSwitchRoom}
                onRenameRoom={rooms.renameRoom}
                onDeleteRoom={onDeleteRoom}
                onBlockedRename={() => showToast("⚠ 응답 중에는 이 채팅방의 이름을 변경할 수 없습니다.\n응답이 끝난 뒤 다시 시도해주세요.")}
                modelNameList={modelNameList}
                defaultModelName={defaultModelName}
                onModelChange={(modelName) => activeRoom && rooms.setRoomModel(activeRoom.roomId, modelName)}
                onReasoningEffortChange={(reasoningEffort) => activeRoom && rooms.setRoomReasoningEffort(activeRoom.roomId, reasoningEffort)}
                isDeveloperMode={isDeveloperMode}
                onToggleDeveloperMode={onToggleDeveloperMode}
                apiUrlText={apiUrlText}
                onApiUrlChange={onApiUrlChange}
                onResetSession={() => { if (!isStreaming) setIsResetModalOpen(true); }}
                onLogout={logout}
            />

            <main className="flex-1 flex flex-col min-h-0 min-w-0">
                <ChatHeader room={activeRoom} statusText={statusInfo.text} statusToneClass={statusInfo.toneClass}
                            isDarkTheme={isDarkTheme} onToggleTheme={toggleTheme} />

                <ChatMessageList
                    room={activeRoom}
                    messageList={activeRoom ? activeRoom.messages : []}
                    streamingState={stream.streamingState}
                    isStreaming={isStreaming}
                    isDeveloperMode={isDeveloperMode}
                    isBookmarked={bookmarks.isBookmarked}
                    onToggleBookmark={bookmarks.toggleBookmark}
                    onSubmitEdit={onSubmitEdit}
                    onBlockedEdit={() => showToast("⚠ 응답 중에는 질문을 수정할 수 없습니다.")}
                    onRetryError={onRetryError}
                    scrollTargetAgentIndex={scrollTargetAgentIndex}
                    isSpeechSupported={tts.isSpeechSupported}
                    speakingKey={tts.speakingKey}
                    onToggleSpeak={tts.toggleSpeak}
                    onQuoteText={onQuoteText}
                />

                <ChatInput inputValue={inputValue} onInputValueChange={setInputValue}
                           onSend={onSend} onStop={stream.stopStreaming} isStreaming={isStreaming}
                           referencedText={referencedText} onClearReference={() => setReferencedText("")} />
            </main>

            <ToastContainer toastList={toastList} onDismiss={dismissToast} />
            <ResetConfirmModal isOpen={isResetModalOpen} onCancel={() => setIsResetModalOpen(false)} onConfirm={onConfirmReset} />
        </div>
    );
}
