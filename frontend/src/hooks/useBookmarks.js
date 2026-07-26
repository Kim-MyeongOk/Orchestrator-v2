import { useCallback } from "react";
import { useEffect }   from "react";
import { useRef }      from "react";
import { useState }    from "react";

import { BOOKMARK_STORAGE_KEY } from "../constants/storageKeys";
import { readJsonFromStorage }  from "../constants/storageKeys";
import { writeJsonToStorage }   from "../constants/storageKeys";

import { deleteBookmarkAsync }     from "../api/chatApi";
import { getUserId }               from "../api/chatApi";
import { listBookmarksAsync }      from "../api/chatApi";
import { updateBookmarkMemoAsync } from "../api/chatApi";
import { upsertBookmarkAsync }     from "../api/chatApi";

/* 북마크 : 서버(chat_bookmark 테이블)가 원본, localStorage 는 오프라인 폴백 캐시.
   식별 키는 (방, 방 안에서의 에이전트 답변 순번) 조합이다.
   thread_id 는 대화 전체를 가리키는 값이라 답변 하나를 지목할 수 없어 쓰지 않는다.

   쓰기는 낙관적으로 처리한다 — 화면을 먼저 바꾸고 서버 호출은 흘려보낸다(실패해도 되돌리지 않는다).
   토글 응답이 왕복 지연만큼 늦게 반영되면 하트가 뒤늦게 깜빡이는 것처럼 보이기 때문이다. */

function readCachedBookmarkList(currentUserId) {
    const storedValue = readJsonFromStorage(BOOKMARK_STORAGE_KEY, null);
    // 구버전(서버 도입 이전) : 모든 사용자의 북마크가 한 배열에 담기고 항목마다 userId 가 붙어 있었다
    if (Array.isArray(storedValue)) return storedValue.filter(bookmark => bookmark.userId === currentUserId);
    // 신버전 : 현재 사용자 캐시만 담는다
    if (storedValue && Array.isArray(storedValue.bookmarkList) && storedValue.userId === currentUserId) return storedValue.bookmarkList;
    return [];
}

export function useBookmarks({ showToast } = {}) {
    const [bookmarkList, setBookmarkList] = useState([]);

    // 서버 로드가 끝나기 전에는 캐시를 쓰지 않는다 (빈 목록으로 덮어쓰는 것을 방지)
    const isLoadedRef = useRef(false);

    useEffect(() => {
        if (!isLoadedRef.current) return;
        writeJsonToStorage(BOOKMARK_STORAGE_KEY, { bookmarkList, userId : getUserId() });
    }, [bookmarkList]);

    /* ── 최초 로드 : 서버 우선, 실패 시 localStorage 캐시 폴백 ── */

    useEffect(() => {
        let isCancelled = false;

        (async function loadBookmarksAsync() {
            const cachedBookmarkList = readCachedBookmarkList(getUserId());
            let   loadedBookmarkList = [];
            try {
                const serverBookmarkList = await listBookmarksAsync();
                // 캐시에만 있고 서버에 없는 항목은 등록을 시도한다.
                // 서버 도입 이전 데이터의 이관이자, 지난번 실패분(방 등록보다 북마크 등록이 먼저 도착해 403 이 난 경우)의 재시도다.
                const missingBookmarkList = cachedBookmarkList.filter(cachedBookmark =>
                    !serverBookmarkList.some(serverBookmark =>
                        serverBookmark.roomId === cachedBookmark.roomId && serverBookmark.agentIndex === cachedBookmark.agentIndex));
                missingBookmarkList.forEach(missingBookmark => upsertBookmarkAsync(missingBookmark));
                loadedBookmarkList = [...serverBookmarkList, ...missingBookmarkList]
                    .sort((leftBookmark, rightBookmark) => (rightBookmark.createdAt || 0) - (leftBookmark.createdAt || 0));
            } catch (error) {
                loadedBookmarkList = cachedBookmarkList;
                if (showToast) showToast(`⚠ 북마크 서버 연결 실패 (${error.message})\n로컬 캐시로 동작합니다.`);
            }

            if (isCancelled) return;
            isLoadedRef.current = true;
            setBookmarkList(loadedBookmarkList);
        })();

        return () => { isCancelled = true; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    /* ── 조회 ── */

    const isBookmarked = useCallback(
        (roomId, agentIndex) => bookmarkList.some(bookmark => bookmark.roomId === roomId && bookmark.agentIndex === agentIndex),
        [bookmarkList]
    );

    /* ── 토글 ── */

    const toggleBookmark = useCallback((roomId, agentIndex, answerText, completedAtMs) => {
        setBookmarkList(previousList => {
            const existingBookmark = previousList.find(bookmark => bookmark.roomId === roomId && bookmark.agentIndex === agentIndex);
            if (existingBookmark) {
                deleteBookmarkAsync(existingBookmark.bookmarkId);
                return previousList.filter(bookmark => bookmark !== existingBookmark);
            }
            const newBookmark = {
                bookmarkId  : crypto.randomUUID(),
                roomId      : roomId,
                agentIndex  : agentIndex,
                text        : (answerText || "").slice(0, 500),   // 미리보기용 스냅샷
                memo        : "",
                completedAt : completedAtMs || Date.now(),
                createdAt   : Date.now()
            };
            upsertBookmarkAsync(newBookmark);
            return [newBookmark, ...previousList];
        });
    }, []);

    /* ── 메모 수정 ──
       토글과 달리 낙관적 갱신 후 실패하면 되돌린다.
       사용자가 직접 입력한 내용이라 조용히 사라지면 저장된 줄로 오해하기 때문이다. */

    const updateBookmarkMemo = useCallback(async (bookmarkId, memoText) => {
        const normalizedMemo = (memoText || "").trim();
        let   previousMemo   = "";

        setBookmarkList(previousList => previousList.map(bookmark => {
            if (bookmark.bookmarkId !== bookmarkId) return bookmark;
            previousMemo = bookmark.memo || "";
            return { ...bookmark, memo : normalizedMemo };
        }));

        try {
            const savedMemo = await updateBookmarkMemoAsync(bookmarkId, normalizedMemo);
            // 서버가 자른(최대 길이) 결과로 맞춰 둔다
            setBookmarkList(previousList => previousList.map(bookmark =>
                bookmark.bookmarkId === bookmarkId ? { ...bookmark, memo : savedMemo } : bookmark));
            return true;
        } catch (error) {
            setBookmarkList(previousList => previousList.map(bookmark =>
                bookmark.bookmarkId === bookmarkId ? { ...bookmark, memo : previousMemo } : bookmark));
            if (showToast) showToast(`⚠ 메모 저장에 실패했습니다 (${error.message})`);
            return false;
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    /* ── 정리 : 서버에도 같은 규칙이 걸려 있지만(방 삭제 CASCADE · 절단 시 삭제)
         세션 초기화처럼 서버 트리거가 없는 경로가 있어 여기서도 명시적으로 지운다. 두 번 지워도 무해하다. ── */

    const removeBookmarkListLocally = useCallback((matchesRemovalCallable) => {
        setBookmarkList(previousList => {
            const remainingList = previousList.filter(bookmark => !matchesRemovalCallable(bookmark));
            previousList
                .filter(matchesRemovalCallable)
                .forEach(removedBookmark => deleteBookmarkAsync(removedBookmark.bookmarkId));
            return remainingList;
        });
    }, []);

    const removeRoomBookmarks = useCallback((roomId) => {
        removeBookmarkListLocally(bookmark => bookmark.roomId === roomId);
    }, [removeBookmarkListLocally]);

    const removeBookmarksFromAgentIndex = useCallback((roomId, fromAgentIndex) => {
        // 질문 수정으로 대화가 절단된 경우 : 잘려나간 답변들의 북마크를 제거한다 (순번이 어긋나는 것을 방지)
        removeBookmarkListLocally(bookmark => bookmark.roomId === roomId && bookmark.agentIndex >= fromAgentIndex);
    }, [removeBookmarkListLocally]);

    return { bookmarkList, isBookmarked, toggleBookmark, updateBookmarkMemo, removeRoomBookmarks, removeBookmarksFromAgentIndex };
}
