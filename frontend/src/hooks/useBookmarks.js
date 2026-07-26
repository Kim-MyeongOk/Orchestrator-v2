import { useCallback } from "react";
import { useEffect }   from "react";
import { useMemo }     from "react";
import { useState }    from "react";

import { BOOKMARK_STORAGE_KEY } from "../constants/storageKeys";
import { readJsonFromStorage }  from "../constants/storageKeys";
import { writeJsonToStorage }   from "../constants/storageKeys";
import { getUserId }            from "../api/chatApi";

/* 북마크 : 답변 단위 저장 · localStorage 영속화
   식별 키는 (방, 방 안에서의 에이전트 답변 순번) 조합이고, 로그인 사용자별로 분리 보관한다.
   저장소에는 모든 사용자의 북마크가 함께 들어가므로 화면에는 현재 사용자 것만 걸러 보여준다. */

export function useBookmarks() {
    const [allBookmarkList, setAllBookmarkList] = useState(() => {
        const storedList = readJsonFromStorage(BOOKMARK_STORAGE_KEY, []);
        return Array.isArray(storedList) ? storedList : [];
    });

    useEffect(() => { writeJsonToStorage(BOOKMARK_STORAGE_KEY, allBookmarkList); }, [allBookmarkList]);

    const currentUserId = getUserId();

    const bookmarkList = useMemo(
        () => allBookmarkList.filter(bookmark => bookmark.userId === currentUserId),
        [allBookmarkList, currentUserId]
    );

    const isBookmarked = useCallback(
        (roomId, agentIndex) => allBookmarkList.some(bookmark =>
            bookmark.userId === currentUserId && bookmark.roomId === roomId && bookmark.agentIndex === agentIndex),
        [allBookmarkList, currentUserId]
    );

    const toggleBookmark = useCallback((roomId, agentIndex, answerText, completedAtMs) => {
        setAllBookmarkList(previousList => {
            const existingIndex = previousList.findIndex(bookmark =>
                bookmark.userId === currentUserId && bookmark.roomId === roomId && bookmark.agentIndex === agentIndex);
            if (existingIndex !== -1) return previousList.filter((_bookmark, index) => index !== existingIndex);
            const newBookmark = {
                bookmarkId  : crypto.randomUUID(),
                userId      : currentUserId,
                roomId      : roomId,
                agentIndex  : agentIndex,
                text        : (answerText || "").slice(0, 500),   // 미리보기용 스냅샷
                completedAt : completedAtMs || Date.now(),
                createdAt   : Date.now()
            };
            return [newBookmark, ...previousList];
        });
    }, [currentUserId]);

    const removeRoomBookmarks = useCallback((roomId) => {
        // 방 삭제 시 해당 방의 북마크도 함께 정리한다
        setAllBookmarkList(previousList => previousList.filter(bookmark =>
            !(bookmark.userId === currentUserId && bookmark.roomId === roomId)));
    }, [currentUserId]);

    const removeBookmarksFromAgentIndex = useCallback((roomId, fromAgentIndex) => {
        // 질문 수정으로 대화가 절단된 경우 : 잘려나간 답변들의 북마크를 제거한다 (순번이 어긋나는 것을 방지)
        setAllBookmarkList(previousList => previousList.filter(bookmark =>
            !(bookmark.userId === currentUserId && bookmark.roomId === roomId && bookmark.agentIndex >= fromAgentIndex)));
    }, [currentUserId]);

    return { bookmarkList, isBookmarked, toggleBookmark, removeRoomBookmarks, removeBookmarksFromAgentIndex };
}
