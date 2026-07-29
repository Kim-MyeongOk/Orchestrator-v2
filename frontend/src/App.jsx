import { useCallback } from "react";
import { useEffect }   from "react";
import { useRef }      from "react";
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
import { useSTT }        from "./hooks/useSTT";
import { useTheme }      from "./hooks/useTheme";
import { useToast }      from "./hooks/useToast";
import { useTTS }        from "./hooks/useTTS";

import { getApiUrl }             from "./api/chatApi";
import { getAuthToken }          from "./api/chatApi";
import { getUserId }             from "./api/chatApi";
import { listModelsAsync }       from "./api/chatApi";
import { logout }                from "./api/chatApi";
import { setApiUrl }              from "./api/chatApi";
import { takeLogoutReasonText }   from "./api/chatApi";
import { truncateThreadAsync }    from "./api/chatApi";
import { uploadImageAsync }       from "./api/chatApi";

import { DEVELOPER_MODE_STORAGE_KEY } from "./constants/storageKeys";
import { INPUT_DRAFT_STORAGE_KEY }    from "./constants/storageKeys";

const IDLE_STATUS      = { text : "대기",   toneClass : "bg-slate-400 dark:bg-slate-600" };
const STREAMING_STATUS = { text : "응답 중", toneClass : "bg-emerald-400 animate-pulse" };

const REFERENCE_MAXIMUM_COUNT          = 10;   // 한 번에 담을 수 있는 답변 참조 개수 (서버 상한과 맞춘다)
const REFERENCE_PREVIEW_MAXIMUM_LENGTH = 120;  // 칩 툴팁에 보여줄 답변 미리보기 길이
const IMAGE_ATTACHMENT_MAXIMUM_COUNT   = 5;    // 한 질문에 붙일 수 있는 이미지 수 (서버 VisionMessageBuilder 와 맞춘다)

// 세션 만료 안내 문구는 모듈이 로드될 때 한 번만 꺼내 온다.
// 컴포넌트 안에서 꺼내면 StrictMode 의 이중 마운트 때 첫 마운트가 값을 소비해 버리고,
// 실제로 화면에 남는 두 번째 마운트는 빈 값을 읽어 안내가 뜨지 않는다.
const INITIAL_LOGOUT_REASON_TEXT = takeLogoutReasonText();

export default function App() {
    const { isDarkTheme, toggleTheme }            = useTheme();
    const { toastList, showToast, dismissToast }  = useToast();

    // 세션이 만료돼 로그인 페이지로 튕겼다 돌아와도 쓰던 문장을 잃지 않도록 초안을 복원한다
    const [inputValue, setInputValue]                     = useState(() => localStorage.getItem(INPUT_DRAFT_STORAGE_KEY) || "");
    const [referencedText, setReferencedText]             = useState("");   // 답변에서 「참조하기」로 담은 발췌 (전송 후 비운다)
    // 우클릭으로 통째로 담은 이전 답변들 : [{ messageId, agentIndex, previewText }] (전송 후 비운다)
    const [selectedReferenceList, setSelectedReferenceList] = useState([]);
    // 첨부한 이미지들 : [{ attachmentId, fileName, previewUrl, imageUrl, isUploading, errorText }] (전송 후 비운다)
    const [attachedImageList, setAttachedImageList]         = useState([]);
    // 생각 정도는 방(room)별 값이라 여기서 들고 있지 않는다 — 톱니바퀴의 열림 상태만 관리한다
    const [isEffortSettingsOpen, setIsEffortSettingsOpen] = useState(false);
    const [sidebarTabName, setSidebarTabName]             = useState("rooms");
    const [isResetModalOpen, setIsResetModalOpen]         = useState(false);
    const [scrollTargetAgentIndex, setScrollTargetAgentIndex] = useState(null);
    const [statusInfo, setStatusInfo]                     = useState(IDLE_STATUS);
    const [apiUrlText, setApiUrlText]                     = useState(getApiUrl());
    const [modelNameList, setModelNameList]               = useState([]);
    const [visionModelNameList, setVisionModelNameList]   = useState([]);   // 이미지 첨부가 가능한 모델
    const [defaultModelName, setDefaultModelName]         = useState("");
    const [isDeveloperMode, setIsDeveloperMode]           = useState(
        () => localStorage.getItem(DEVELOPER_MODE_STORAGE_KEY) === "on"
    );

    // 전송 중에는 초안 자동 삭제를 막는다 (401 로 튕길 때 보낸 문장을 되살리기 위함)
    const isSendInFlightRef = useRef(false);

    const rooms     = useRooms({ showToast });
    const bookmarks = useBookmarks({ showToast });
    // speechSynthesis 는 창 전체에 하나뿐이라 훅도 여기서 한 번만 만든다 (말풍선마다 두면 재생 상태가 어긋난다)
    const tts       = useTTS();
    // 마이크도 하나뿐이라 같은 이유로 여기서 만든다. 인식 결과는 입력창 값으로 곧장 흘려보낸다.
    const stt       = useSTT({ onTranscriptChange : setInputValue, onError : showToast });

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

    /* ── 세션 만료 대비 : 입력 초안 보관 + 만료 안내 ── */

    // 입력할 때마다 초안을 남긴다. 401 로 튕겨도 다시 들어오면 그대로 이어서 쓸 수 있다.
    //
    // 전송으로 입력창이 비는 경우에는 초안을 지우지 않는다.
    // 전송이 401 로 끝나면 방금 보낸 문장까지 잃어버리기 때문이다 (지우는 시점은 턴이 끝난 뒤).
    useEffect(() => {
        if (inputValue) { localStorage.setItem(INPUT_DRAFT_STORAGE_KEY, inputValue); return; }
        if (!isSendInFlightRef.current) localStorage.removeItem(INPUT_DRAFT_STORAGE_KEY);
    }, [inputValue]);

    // 세션 만료로 로그아웃됐던 경우에만 사유를 한 번 안내한다 (직접 로그아웃한 경우에는 뜨지 않는다)
    useEffect(() => {
        if (INITIAL_LOGOUT_REASON_TEXT) showToast(`⚠ ${INITIAL_LOGOUT_REASON_TEXT}`);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    /* ── 모델 목록 : 백엔드보다 페이지를 먼저 연 경우를 위해 지수 백오프로 재시도한다 ── */

    useEffect(() => {
        let isCancelled  = false;
        let retryTimerId = null;

        const loadModelOptionsAsync = async (attemptCount = 0) => {
            try {
                const { defaultModel, modelNameList : loadedModelNameList, visionModelNameList : loadedVisionModelNameList } = await listModelsAsync();
                if (isCancelled) return;
                setDefaultModelName(defaultModel);
                setModelNameList(loadedModelNameList);
                setVisionModelNameList(loadedVisionModelNameList);
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

    /* ── 생각 정도 (톱니바퀴 설정) ── */

    // 방별 값이라 방에 저장한다. 빈 문자열이면 모델 기본 동작을 따른다.
    const onReasoningEffortChange = useCallback((nextReasoningEffort) => {
        if (!activeRoom) return;
        rooms.setRoomReasoningEffort(activeRoom.roomId, nextReasoningEffort);
    }, [activeRoom, rooms]);

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

        // 업로드가 끝나지 않은 이미지가 있으면 기다린다 — 지금 보내면 그 이미지는 빠진 채로 나간다
        if (attachedImageList.some(attachedImage => attachedImage.isUploading)) {
            showToast("⚠ 이미지 업로드가 끝난 뒤에 전송해주세요.");
            return;
        }
        const uploadedImageUrlList = attachedImageList.filter(attachedImage => attachedImage.imageUrl).map(attachedImage => attachedImage.imageUrl);

        const sentTurnOption = {
            referencedText          : referencedText,
            referencedMessageIdList : selectedReferenceList.map(reference => reference.messageId),
            imageUrlList            : uploadedImageUrlList
        };
        stt.stopRecording();   // 받아쓰기가 켜진 채로 두면 방금 비운 입력창에 보낸 문장이 되살아난다
        isSendInFlightRef.current = true;   // 턴이 끝날 때까지 초안을 지키게 한다
        setInputValue("");
        // 참조는 한 턴만 따라간다 (다음 질문에 의도치 않게 달라붙지 않도록).
        // 프리셋은 유지한다 (사용자가 명시적으로 바꿀 때까지).
        setReferencedText("");
        setSelectedReferenceList([]);
        // 미리보기 URL 은 여기서 해제한다 — 말풍선은 MinIO URL 로 다시 그리므로 blob 이 필요 없다
        attachedImageList.forEach(attachedImage => URL.revokeObjectURL(attachedImage.previewUrl));
        setAttachedImageList([]);
        const finalStatus = await stream.sendMessageAsync(activeRoom, messageText, sentTurnOption);
        isSendInFlightRef.current = false;
        // 턴 도중 401 로 로그아웃됐으면 초안을 남겨 둔다 (다시 로그인하면 그대로 이어서 쓸 수 있다).
        // location.replace() 는 실행을 즉시 멈추지 않아 이 줄까지 흘러오므로, 토큰이 남아 있는지로 판별한다.
        if (getAuthToken()) localStorage.removeItem(INPUT_DRAFT_STORAGE_KEY);
        setStatusInfo(finalStatus);
    }, [activeRoom, attachedImageList, inputValue, isStreaming, referencedText, selectedReferenceList, showToast, stream, stt]);

    const onRetryError = useCallback(async (errorMessage) => {
        if (isStreaming || !activeRoom) return;
        rooms.removeErrorMessage(activeRoom.roomId, errorMessage.text);
        // 실패한 턴에 붙어 있던 참조와 프리셋을 그대로 다시 실어 보낸다
        const finalStatus = await stream.executeStreamTurnAsync(activeRoom, errorMessage.retryMessageText, errorMessage.retryTurnOption || {});
        setStatusInfo(finalStatus);
    }, [activeRoom, isStreaming, rooms, stream]);

    /* ── 참조하기 : 답변에서 드래그한 구간을 다음 질문의 문맥으로 담아 둔다 ── */

    const onQuoteText = useCallback((selectedText) => {
        if (isStreaming) { showToast("⚠ 응답 중에는 참조를 담을 수 없습니다."); return; }
        setReferencedText(selectedText);
    }, [isStreaming, showToast]);

    /* ── 답변 다중 참조 : 답변을 우클릭해 통째로 담고/뺀다 ── */

    const onToggleReference = useCallback((agentIndex, answerText) => {
        if (isStreaming) { showToast("⚠ 응답 중에는 참조를 담을 수 없습니다."); return; }
        setSelectedReferenceList(previousList => {
            if (previousList.some(reference => reference.agentIndex === agentIndex)) {
                return previousList.filter(reference => reference.agentIndex !== agentIndex);
            }
            if (previousList.length >= REFERENCE_MAXIMUM_COUNT) {
                showToast(`⚠ 참조는 최대 ${REFERENCE_MAXIMUM_COUNT}개까지 담을 수 있습니다.`);
                return previousList;
            }
            // 담은 순서를 유지한다 — 칩이 눌린 순서대로 늘어서야 어떤 걸 방금 담았는지 알아보기 쉽다
            return [...previousList, {
                messageId   : `agent-${agentIndex}`,
                agentIndex  : agentIndex,
                previewText : (answerText || "").replace(/\s+/g, " ").trim().slice(0, REFERENCE_PREVIEW_MAXIMUM_LENGTH)
            }];
        });
    }, [isStreaming, showToast]);

    const onRemoveReference = useCallback((agentIndex) => {
        setSelectedReferenceList(previousList => previousList.filter(reference => reference.agentIndex !== agentIndex));
    }, []);

    const onClearAllReferences = useCallback(() => {
        setSelectedReferenceList([]);
        setReferencedText("");
    }, []);

    /* ── 이미지 첨부 : MinIO 에 올리고 발급된 URL 을 질문과 함께 보낸다 ── */

    const onRemoveImage = useCallback((attachmentId) => {
        setAttachedImageList(previousList => {
            const removedImage = previousList.find(attachedImage => attachedImage.attachmentId === attachmentId);
            // createObjectURL 로 만든 미리보기는 직접 해제해야 메모리에서 사라진다
            if (removedImage) URL.revokeObjectURL(removedImage.previewUrl);
            return previousList.filter(attachedImage => attachedImage.attachmentId !== attachmentId);
        });
    }, []);

    // 현재 방의 모델이 이미지를 읽을 수 있는지 (목록을 아직 못 받았으면 막지 않는다)
    const activeModelName  = activeRoom?.model || defaultModelName;
    const isVisionSupported = visionModelNameList.length === 0 || visionModelNameList.includes(activeModelName);

    const onAttachImageFileList = useCallback(async (fileList) => {
        if (isStreaming) { showToast("⚠ 응답 중에는 이미지를 첨부할 수 없습니다."); return; }
        // 보내 봐야 서버가 프롬프트에서 걷어내므로, 조용히 무시되기 전에 여기서 막고 알린다
        if (!isVisionSupported) { showToast(`⚠ ${activeModelName} 모델은 이미지를 읽지 못합니다.
비전 모델로 바꾼 뒤 첨부해주세요.`); return; }

        const imageFileList = fileList.filter(file => file.type.startsWith("image/"));
        if (imageFileList.length < fileList.length) showToast("⚠ 이미지 파일만 첨부할 수 있습니다.");
        if (imageFileList.length === 0) return;

        // 먼저 로컬 미리보기를 띄우고(업로드를 기다리지 않는다) 업로드 결과로 각 항목을 갱신한다
        const pendingImageList = imageFileList.slice(0, IMAGE_ATTACHMENT_MAXIMUM_COUNT).map(imageFile => ({
            attachmentId : `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            fileName     : imageFile.name,
            previewUrl   : URL.createObjectURL(imageFile),
            imageUrl     : "",
            isUploading  : true,
            errorText    : ""
        }));

        setAttachedImageList(previousList => {
            const remainingSlotCount = IMAGE_ATTACHMENT_MAXIMUM_COUNT - previousList.length;
            if (remainingSlotCount <= 0) {
                showToast(`⚠ 이미지는 최대 ${IMAGE_ATTACHMENT_MAXIMUM_COUNT}장까지 첨부할 수 있습니다.`);
                pendingImageList.forEach(pendingImage => URL.revokeObjectURL(pendingImage.previewUrl));
                return previousList;
            }
            return [...previousList, ...pendingImageList.slice(0, remainingSlotCount)];
        });

        for (const [pendingIndex, pendingImage] of pendingImageList.entries()) {
            try {
                const { imageUrl } = await uploadImageAsync(imageFileList[pendingIndex]);
                setAttachedImageList(previousList => previousList.map(attachedImage =>
                    attachedImage.attachmentId === pendingImage.attachmentId
                        ? { ...attachedImage, imageUrl : imageUrl, isUploading : false }
                        : attachedImage));
            } catch (uploadError) {
                setAttachedImageList(previousList => previousList.map(attachedImage =>
                    attachedImage.attachmentId === pendingImage.attachmentId
                        ? { ...attachedImage, isUploading : false, errorText : uploadError.message }
                        : attachedImage));
                showToast(`⚠ ${pendingImage.fileName} 업로드 실패 : ${uploadError.message}`);
            }
        }
    }, [isStreaming, isVisionSupported, activeModelName, showToast]);

    /* ── 음성 받아쓰기 : 인식 결과를 입력창에 이어 붙인다 ── */

    const onToggleRecording = useCallback(() => {
        // 답변을 읽어주는 중이면 먼저 끊는다 — 스피커로 나가는 소리를 마이크가 그대로 받아 적는다
        if (!stt.isRecording) tts.stopSpeaking();
        stt.toggleRecording(inputValue);   // 이미 적어둔 글 뒤에 이어 붙이도록 현재 입력값을 넘긴다
    }, [inputValue, stt, tts]);

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

        // 잘려나간 답변을 가리키던 참조도 함께 정리한다 (칩에 남은 번호가 엉뚱한 답변을 가리키게 된다)
        setSelectedReferenceList(previousList => previousList.filter(reference => reference.agentIndex < keptAgentMessageCount));
        setReferencedText("");

        // ③ 수정된 질문으로 그 지점부터 대화를 이어간다 (프리셋은 지금 고른 값을 유지한다)
        const finalStatus = await stream.sendMessageAsync({ ...activeRoom, messages : keptMessageList }, editedText, {});
        setStatusInfo(finalStatus);
    }, [activeRoom, bookmarks, isStreaming, rooms, showToast, stream]);

    /* ── 방 조작 ── */

    // 새 방 만들기·방 삭제도 결국 보고 있는 방이 바뀐다.
    // 이 둘은 onSwitchRoom 을 거치지 않으므로 받아쓰기 정지를 여기서 따로 걸어준다
    // (안 걸면 마이크가 켜진 채로 새 방에 넘어가 그 방 입력창에 계속 받아 적힌다).
    // 참조는 "이 방의 몇 번째 답변"이라 방을 옮기면 뜻을 잃는다. 방이 바뀌는 모든 길목에서 비운다.
    const clearRoomScopedReference = useCallback(() => {
        setReferencedText("");
        setSelectedReferenceList([]);
        setAttachedImageList(previousList => {
            previousList.forEach(attachedImage => URL.revokeObjectURL(attachedImage.previewUrl));
            return [];
        });
    }, []);

    const onCreateRoom = useCallback(() => {
        stt.stopRecording();
        clearRoomScopedReference();
        rooms.createRoom();
    }, [clearRoomScopedReference, rooms, stt]);

    const onSwitchRoom = useCallback((roomId) => {
        if (isStreaming) { showToast("⚠ 응답 중에는 다른 대화로 이동할 수 없습니다."); return; }
        tts.stopSpeaking();   // 떠난 방의 답변을 계속 읽으면 정지 버튼이 화면에 없어 멈출 방법이 없다
        stt.stopRecording();  // 받아쓰기도 끊는다 — 다른 방 입력창에 이어서 받아 적히면 안 된다
        clearRoomScopedReference();
        setScrollTargetAgentIndex(null);
        rooms.switchRoom(roomId);
    }, [clearRoomScopedReference, isStreaming, rooms, showToast, stt, tts]);

    const onDeleteRoom = useCallback((roomId) => {
        if (isStreaming) return;
        stt.stopRecording();   // 보고 있던 방을 지우면 다른 방으로 넘어간다 — 마이크를 들고 가지 않는다
        clearRoomScopedReference();
        bookmarks.removeRoomBookmarks(roomId);   // 삭제된 방의 북마크도 함께 정리
        rooms.deleteRoom(roomId);
    }, [bookmarks, clearRoomScopedReference, isStreaming, rooms, stt]);

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
                onCreateRoom={onCreateRoom}
                onSwitchRoom={onSwitchRoom}
                onRenameRoom={rooms.renameRoom}
                onDeleteRoom={onDeleteRoom}
                onBlockedRename={() => showToast("⚠ 응답 중에는 이 채팅방의 이름을 변경할 수 없습니다.\n응답이 끝난 뒤 다시 시도해주세요.")}
                modelNameList={modelNameList}
                defaultModelName={defaultModelName}
                onModelChange={(modelName) => activeRoom && rooms.setRoomModel(activeRoom.roomId, modelName)}
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
                    selectedReferenceList={selectedReferenceList}
                    onToggleReference={onToggleReference}
                />

                <ChatInput inputValue={inputValue} onInputValueChange={setInputValue}
                           onSend={onSend} onStop={stream.stopStreaming} isStreaming={isStreaming}
                           referencedText={referencedText} onClearReference={() => setReferencedText("")}
                           selectedReferenceList={selectedReferenceList}
                           onRemoveReference={onRemoveReference} onClearAllReferences={onClearAllReferences}
                           attachedImageList={attachedImageList}
                           isUploadingImage={attachedImageList.some(attachedImage => attachedImage.isUploading)}
                           onAttachImageFileList={onAttachImageFileList} onRemoveImage={onRemoveImage}
                           isVisionSupported={isVisionSupported} activeModelName={activeModelName}
                           reasoningEffort={activeRoom?.reasoningEffort || ""} onReasoningEffortChange={onReasoningEffortChange}
                           isEffortSettingsOpen={isEffortSettingsOpen} onToggleEffortSettingsOpen={setIsEffortSettingsOpen}
                           isEffortSettingsDisabled={!activeRoom}
                           isRecognitionSupported={stt.isRecognitionSupported} isRecording={stt.isRecording} onToggleRecording={onToggleRecording} />
            </main>

            <ToastContainer toastList={toastList} onDismiss={dismissToast} />
            <ResetConfirmModal isOpen={isResetModalOpen} onCancel={() => setIsResetModalOpen(false)} onConfirm={onConfirmReset} />
        </div>
    );
}
