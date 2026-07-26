import { useCallback } from "react";
import { useEffect }   from "react";
import { useRef }      from "react";
import { useState }    from "react";

/* 브라우저 내장 SpeechSynthesis 로 답변을 읽어주는 훅 (외부 라이브러리 없음).

   speechSynthesis 는 창 전체에 하나뿐인 싱글턴이라 동시에 두 개를 재생할 수 없다.
   그래서 이 훅은 App 에서 한 번만 만들어 쓰고 "지금 어느 말풍선이 재생 중인가"(speakingKey)를
   한 곳에서 관리한다. 말풍선마다 훅을 두면 B 를 눌렀을 때 A 가 취소되는데도
   A 의 버튼은 정지 아이콘으로 남아 정지 버튼이 두 개 보인다.

   긴 텍스트를 한 번에 넘기면 Chrome 이 15 초 언저리에서 임의로 끊는 알려진 버그가 있다.
   LLM 답변은 그보다 길기 때문에 문장 단위로 잘라 순서대로 재생해 이를 피한다. */

const MAXIMUM_CHUNK_LENGTH = 180;

function splitTextIntoSpeechChunkList(speechText) {
    // 문장 끝(. ! ? 줄바꿈) 으로 자르고, 그래도 긴 문장은 길이로 다시 자른다
    const sentenceList = speechText.match(/[^.!?。？！\n]+[.!?。？！\n]*/g) || [];
    const chunkList    = [];
    sentenceList.forEach(sentence => {
        const trimmedSentence = sentence.trim();
        if (trimmedSentence === "") return;
        if (trimmedSentence.length <= MAXIMUM_CHUNK_LENGTH) {
            chunkList.push(trimmedSentence);
            return;
        }
        for (let startIndex = 0; startIndex < trimmedSentence.length; startIndex += MAXIMUM_CHUNK_LENGTH) {
            chunkList.push(trimmedSentence.slice(startIndex, startIndex + MAXIMUM_CHUNK_LENGTH));
        }
    });
    return chunkList;
}

function selectKoreanVoice(voiceList) {
    // ko-KR 정확히 일치 → 그 외 한국어(ko_KR 등 표기 차이 포함) → 없으면 null (브라우저 기본 음성에 맡긴다)
    const normalizeLanguage = voice => (voice.lang || "").toLowerCase().replace("_", "-");
    return voiceList.find(voice => normalizeLanguage(voice) === "ko-kr")
        || voiceList.find(voice => normalizeLanguage(voice).startsWith("ko"))
        || null;
}

export function useTTS() {
    const isSpeechSupported = typeof window !== "undefined" && "speechSynthesis" in window;

    const [speakingKey, setSpeakingKey] = useState(null);

    const koreanVoiceRef     = useRef(null);
    const speakingKeyRef     = useRef(null);   // 콜백 안에서 최신 값을 읽기 위한 사본
    const speechSessionIdRef = useRef(0);      // 재생 세대 번호 — 아래 stopSpeaking 주석 참고

    /* ── 음성 목록 : 최초 getVoices() 가 빈 배열인 브라우저가 있어 voiceschanged 도 함께 듣는다 ── */

    useEffect(() => {
        if (!isSpeechSupported) return undefined;
        const loadVoiceList = () => { koreanVoiceRef.current = selectKoreanVoice(window.speechSynthesis.getVoices()); };
        loadVoiceList();
        window.speechSynthesis.addEventListener("voiceschanged", loadVoiceList);
        return () => window.speechSynthesis.removeEventListener("voiceschanged", loadVoiceList);
    }, [isSpeechSupported]);

    /* ── 정지 ── */

    const stopSpeaking = useCallback(() => {
        if (!isSpeechSupported) return;
        // 세대 번호를 올려 "이전 재생의 콜백"을 무효화한다.
        // cancel() 은 취소된 utterance 의 onend/onerror 를 뒤늦게 발생시키는데,
        // A 를 멈추고 B 를 트는 순간 그 늦은 콜백이 B 의 재생 상태를 지워버리기 때문이다.
        speechSessionIdRef.current += 1;
        speakingKeyRef.current      = null;
        window.speechSynthesis.cancel();
        setSpeakingKey(null);
    }, [isSpeechSupported]);

    /* ── 재생 ── */

    const startSpeaking = useCallback((speechKey, speechText) => {
        if (!isSpeechSupported) return;
        const chunkList = splitTextIntoSpeechChunkList(speechText || "");
        if (chunkList.length === 0) return;

        stopSpeaking();   // 재생 중인 다른 답변을 끊는다 (싱글턴이라 어차피 동시 재생이 안 된다)

        const currentSessionId = speechSessionIdRef.current;
        speakingKeyRef.current = speechKey;
        setSpeakingKey(speechKey);

        let chunkIndex = 0;

        const finishSpeaking = () => {
            if (speechSessionIdRef.current !== currentSessionId) return;   // 이미 다른 재생이 시작됨
            speakingKeyRef.current = null;
            setSpeakingKey(null);
        };

        const speakNextChunk = () => {
            if (speechSessionIdRef.current !== currentSessionId) return;
            if (chunkIndex >= chunkList.length) { finishSpeaking(); return; }

            const utterance = new SpeechSynthesisUtterance(chunkList[chunkIndex]);
            if (koreanVoiceRef.current) utterance.voice = koreanVoiceRef.current;
            utterance.lang    = koreanVoiceRef.current ? koreanVoiceRef.current.lang : "ko-KR";
            utterance.rate    = 1;
            utterance.pitch   = 1;
            utterance.onend   = () => { chunkIndex += 1; speakNextChunk(); };
            utterance.onerror = finishSpeaking;   // cancel() 로 인한 interrupted 포함 — 세대 번호가 걸러준다
            window.speechSynthesis.speak(utterance);
        };
        speakNextChunk();
    }, [isSpeechSupported, stopSpeaking]);

    /* ── 토글 : 같은 답변을 다시 누르면 정지, 다른 답변이면 그쪽으로 전환 ── */

    const toggleSpeak = useCallback((speechKey, speechText) => {
        if (speakingKeyRef.current === speechKey) stopSpeaking();
        else                                      startSpeaking(speechKey, speechText);
    }, [startSpeaking, stopSpeaking]);

    // 언마운트(로그아웃·새로고침) 시 재생을 끊는다 — 안 끊으면 화면이 사라져도 계속 읽는다
    useEffect(() => () => { if (isSpeechSupported) window.speechSynthesis.cancel(); }, [isSpeechSupported]);

    return { isSpeechSupported, speakingKey, toggleSpeak, stopSpeaking };
}
