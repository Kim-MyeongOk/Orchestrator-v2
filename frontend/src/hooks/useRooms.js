import { useCallback } from "react";
import { useEffect }   from "react";
import { useMemo }     from "react";
import { useRef }      from "react";
import { useState }    from "react";

import { ROOM_STORAGE_KEY }    from "../constants/storageKeys";
import { readJsonFromStorage } from "../constants/storageKeys";
import { writeJsonToStorage }  from "../constants/storageKeys";

import { deleteRoomAsync }        from "../api/chatApi";
import { getThreadMessagesAsync } from "../api/chatApi";
import { getUserId }              from "../api/chatApi";
import { listRoomsAsync }         from "../api/chatApi";
import { upsertRoomAsync }        from "../api/chatApi";

/* 채팅방 상태 : 서버(chat_room 테이블)가 원본, localStorage 는 오프라인 폴백 캐시.
   room = { roomId, threadId, title, model, reasoningEffort, lastRunId?, messages }
   messages = null 이면 "아직 서버에서 안 불러온 방"(lazy 로드 대상), [] 면 빈 대화다. */

function createEmptyRoom() {
    return {
        roomId          : crypto.randomUUID(),
        threadId        : crypto.randomUUID(),
        title           : "새 대화",
        model           : "",
        reasoningEffort : "",
        messages        : []
    };
}

export function useRooms({ showToast }) {
    const [roomList, setRoomList]         = useState([]);
    const [activeRoomId, setActiveRoomId] = useState(null);
    const [isRoomsLoading, setIsRoomsLoading] = useState(true);

    const activeRoom = useMemo(
        () => roomList.find(room => room.roomId === activeRoomId) || null,
        [roomList, activeRoomId]
    );

    // 방 목록 로드가 끝나기 전에는 저장하지 않는다 (빈 목록으로 캐시를 덮어쓰는 것을 방지)
    const isLoadedRef = useRef(false);

    useEffect(() => {
        if (!isLoadedRef.current) return;
        writeJsonToStorage(ROOM_STORAGE_KEY, { roomList, activeRoomId, userId : getUserId() });
    }, [roomList, activeRoomId]);

    /* ── 방 단위 부분 갱신 헬퍼 ── */

    const updateRoom = useCallback((roomId, updateRoomCallable) => {
        setRoomList(previousList => previousList.map(room => (room.roomId === roomId ? updateRoomCallable(room) : room)));
    }, []);

    /* ── 최초 로드 : 서버 우선, 실패 시 localStorage 캐시 폴백 ── */

    useEffect(() => {
        let isCancelled = false;

        (async function loadRoomsAsync() {
            const currentUserId = getUserId();
            const cachedState   = readJsonFromStorage(ROOM_STORAGE_KEY, null);
            const isCacheOwnedByCurrentUser = cachedState
                && (cachedState.userId === undefined || cachedState.userId === currentUserId)
                && Array.isArray(cachedState.roomList);

            let loadedRoomList = [];
            try {
                const serverRoomList = await listRoomsAsync();
                if (serverRoomList.length === 0 && isCacheOwnedByCurrentUser && cachedState.roomList.length > 0) {
                    // 최초 1회 마이그레이션 : 서버 도입 이전의 로컬 방 목록을 이 사용자 ID 로 서버에 등록한다
                    loadedRoomList = cachedState.roomList;
                    loadedRoomList.forEach(localRoom => upsertRoomAsync(localRoom));
                } else {
                    // 로컬 캐시에 같은 방이 있으면 메시지 캐시를 승계한다 (없으면 lazy 로드 대상 = null)
                    loadedRoomList = serverRoomList.map(serverRoom => {
                        const cachedRoom = isCacheOwnedByCurrentUser
                            ? cachedState.roomList.find(room => room.roomId === serverRoom.roomId)
                            : null;
                        return { ...serverRoom, lastRunId : cachedRoom?.lastRunId, messages : cachedRoom?.messages ?? null };
                    });
                }
            } catch (error) {
                // 서버 불가 : 같은 유저의 로컬 캐시로 폴백 (없으면 빈 목록)
                loadedRoomList = isCacheOwnedByCurrentUser ? cachedState.roomList : [];
                showToast(`⚠ 방 목록 서버 연결 실패 (${error.message})\n로컬 캐시로 동작합니다.`);
            }

            if (isCancelled) return;

            if (loadedRoomList.length === 0) {
                const newRoom = createEmptyRoom();
                upsertRoomAsync(newRoom);
                loadedRoomList = [newRoom];
            }
            const restoredActiveRoomId = loadedRoomList.some(room => room.roomId === cachedState?.activeRoomId)
                ? cachedState.activeRoomId
                : loadedRoomList[0].roomId;

            isLoadedRef.current = true;
            setRoomList(loadedRoomList);
            setActiveRoomId(restoredActiveRoomId);
            setIsRoomsLoading(false);
        })();

        return () => { isCancelled = true; };
    }, [showToast]);

    /* ── 체크포인트에서 대화 복원 (messages === null 인 방) ── */

    const restoreRoomMessagesAsync = useCallback(async (room) => {
        let restoredMessageList = [];
        try {
            restoredMessageList = await getThreadMessagesAsync(room.threadId);
        } catch (error) {
            showToast(`⚠ 대화 복원 실패 (${error.message}) — 빈 대화로 시작합니다.`);
        }
        updateRoom(room.roomId, storedRoom => ({ ...storedRoom, messages : restoredMessageList }));
    }, [showToast, updateRoom]);

    // 활성 방의 메시지가 아직 없으면(null) 서버에서 자동 복원한다
    const restoringThreadIdRef = useRef(null);
    useEffect(() => {
        if (!activeRoom || activeRoom.messages !== null) return;
        if (restoringThreadIdRef.current === activeRoom.threadId) return;   // 중복 요청 방지
        restoringThreadIdRef.current = activeRoom.threadId;
        restoreRoomMessagesAsync(activeRoom);
    }, [activeRoom, restoreRoomMessagesAsync]);

    /* ── CRUD ── */

    const createRoom = useCallback(() => {
        const newRoom = createEmptyRoom();
        setRoomList(previousList => [newRoom, ...previousList]);
        setActiveRoomId(newRoom.roomId);
        upsertRoomAsync(newRoom);
    }, []);

    const switchRoom = useCallback((roomId) => { setActiveRoomId(roomId); }, []);

    const renameRoom = useCallback((roomId, newTitleText) => {
        const trimmedTitle = (newTitleText || "").trim().slice(0, 60);
        if (!trimmedTitle) return;
        updateRoom(roomId, room => {
            if (room.title === trimmedTitle) return room;
            const renamedRoom = { ...room, title : trimmedTitle };
            upsertRoomAsync(renamedRoom);
            return renamedRoom;
        });
    }, [updateRoom]);

    const deleteRoom = useCallback((roomId) => {
        deleteRoomAsync(roomId);
        setRoomList(previousList => {
            const remainingRoomList = previousList.filter(room => room.roomId !== roomId);
            if (remainingRoomList.length === 0) {
                const newRoom = createEmptyRoom();
                upsertRoomAsync(newRoom);
                setActiveRoomId(newRoom.roomId);
                return [newRoom];
            }
            setActiveRoomId(previousActiveRoomId => (previousActiveRoomId === roomId ? remainingRoomList[0].roomId : previousActiveRoomId));
            return remainingRoomList;
        });
    }, []);

    const resetActiveSession = useCallback(() => {
        // 새 Thread 발급 (체크포인트와 분리) + 대화 초기화
        if (!activeRoomId) return;
        updateRoom(activeRoomId, room => {
            const resetRoom = { ...room, threadId : crypto.randomUUID(), messages : [], title : "새 대화", lastRunId : undefined };
            upsertRoomAsync(resetRoom);
            return resetRoom;
        });
    }, [activeRoomId, updateRoom]);

    /* ── 방 설정 변경 ── */

    const setRoomModel = useCallback((roomId, modelName) => {
        updateRoom(roomId, room => {
            const updatedRoom = { ...room, model : modelName };
            upsertRoomAsync(updatedRoom);
            return updatedRoom;
        });
    }, [updateRoom]);

    const setRoomReasoningEffort = useCallback((roomId, reasoningEffort) => {
        // 생각 강도 : google → thinking_budget(low 1024/medium 8192/high 24576), ollama → think 레벨(지원 모델 한정)
        updateRoom(roomId, room => {
            const updatedRoom = { ...room, reasoningEffort : reasoningEffort };
            upsertRoomAsync(updatedRoom);
            return updatedRoom;
        });
    }, [updateRoom]);

    /* ── 메시지 조작 ── */

    const appendMessage = useCallback((roomId, message) => {
        updateRoom(roomId, room => ({ ...room, messages : [...(room.messages || []), message] }));
    }, [updateRoom]);

    const replaceMessages = useCallback((roomId, messageList) => {
        updateRoom(roomId, room => ({ ...room, messages : messageList }));
    }, [updateRoom]);

    const removeErrorMessage = useCallback((roomId, errorText) => {
        updateRoom(roomId, room => ({
            ...room,
            messages : (room.messages || []).filter(storedMessage => !(storedMessage.role === "error" && storedMessage.text === errorText))
        }));
    }, [updateRoom]);

    // 방 제목 자동 지정 : 첫 질문의 앞부분을 제목으로 쓴다
    const applyFirstMessageTitle = useCallback((roomId, messageText) => {
        updateRoom(roomId, room => {
            if (room.title !== "새 대화") return room;
            const titledRoom = { ...room, title : messageText.slice(0, 24) };
            upsertRoomAsync(titledRoom);
            return titledRoom;
        });
    }, [updateRoom]);

    const setRoomLastRunId = useCallback((roomId, runId) => {
        updateRoom(roomId, room => ({ ...room, lastRunId : runId }));
    }, [updateRoom]);

    // 백엔드 프로바이더가 바뀌어 방에 저장된 모델이 무효가 된 경우 기본 모델로 되돌린다
    const dropInvalidRoomModels = useCallback((validModelNameSet) => {
        setRoomList(previousList => {
            let isDirty = false;
            const nextList = previousList.map(room => {
                if (room.model && !validModelNameSet.has(room.model)) { isDirty = true; return { ...room, model : "" }; }
                return room;
            });
            return isDirty ? nextList : previousList;
        });
    }, []);

    return {
        roomList, activeRoomId, activeRoom, isRoomsLoading,
        createRoom, switchRoom, renameRoom, deleteRoom, resetActiveSession,
        setRoomModel, setRoomReasoningEffort, setRoomLastRunId, dropInvalidRoomModels,
        appendMessage, replaceMessages, removeErrorMessage, applyFirstMessageTitle
    };
}
