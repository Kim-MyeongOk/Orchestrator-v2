import { useEffect } from "react";
import { useState }  from "react";

export function formatRelativeTime(completedAtMs) {
    // 답변 완료 시점 기준 상대 시간 : 지금 / N분 전 / N시간 전 / N일 전 / 지난 주 / N주 전 / N개월 전 / N년 전
    const diffSecond = Math.max(0, Math.floor((Date.now() - completedAtMs) / 1000));
    const diffMinute = Math.floor(diffSecond / 60);
    const diffHour   = Math.floor(diffMinute / 60);
    const diffDay    = Math.floor(diffHour   / 24);
    const diffWeek   = Math.floor(diffDay    / 7);
    const diffMonth  = Math.floor(diffDay    / 30);
    const diffYear   = Math.floor(diffDay    / 365);
    if (diffYear   >= 1)  return `${diffYear}년 전`;
    if (diffMonth  >= 1)  return `${diffMonth}개월 전`;
    if (diffDay    >= 14) return `${diffWeek}주 전`;
    if (diffDay    >= 7)  return "지난 주";
    if (diffDay    >= 1)  return `${diffDay}일 전`;
    if (diffHour   >= 1)  return `${diffHour}시간 전`;
    if (diffMinute >= 1)  return `${diffMinute}분 전`;
    return "지금";
}

export function formatFullTimestamp(completedAtMs) {
    // 개발자 모드용 절대 시각(밀리초까지) : 2026-07-25 18:53:40.000
    const dateValue = new Date(completedAtMs);
    const pad = (value, size = 2) => String(value).padStart(size, "0");
    return `${dateValue.getFullYear()}-${pad(dateValue.getMonth() + 1)}-${pad(dateValue.getDate())} `
         + `${pad(dateValue.getHours())}:${pad(dateValue.getMinutes())}:${pad(dateValue.getSeconds())}.${pad(dateValue.getMilliseconds(), 3)}`;
}

/* ── 상대 시간 30초 주기 갱신 ──
   메시지마다 setInterval 을 만들면 낭비이므로, 모듈 단위 타이머 하나를 구독하는 방식으로 공유한다. */

const timeTickSubscriberSet = new Set();
let   timeTickTimerId       = null;

function ensureTimeTickTimerStarted() {
    if (timeTickTimerId !== null) return;
    timeTickTimerId = setInterval(() => timeTickSubscriberSet.forEach(notify => notify()), 30000);
}

export function useTimeTick() {
    const [, setTickCount] = useState(0);
    useEffect(() => {
        const notify = () => setTickCount(previousCount => previousCount + 1);
        timeTickSubscriberSet.add(notify);
        ensureTimeTickTimerStarted();
        return () => { timeTickSubscriberSet.delete(notify); };
    }, []);
}
