import { useCallback } from "react";
import { useEffect }   from "react";
import { useRef }      from "react";
import { useState }    from "react";

/* 브라우저 내장 SpeechRecognition 으로 말을 받아 적는 훅 (외부 라이브러리 없음).

   마이크는 창 전체에 하나뿐이라 TTS 훅과 마찬가지로 App 에서 한 번만 만들어 쓴다.
   (말풍선/입력창마다 두면 두 세션이 같은 마이크를 두고 다툰다)

   받아쓰기 결과를 입력창에 그대로 덮어쓰지 않고 세 조각을 합쳐 만든다.
     baseText(녹음 시작 시점의 입력창 내용) + finalTranscript(확정된 인식 결과) + interim(말하는 중인 조각)
   이렇게 나눈 이유 : 중간 결과(interim)는 다음 이벤트에서 더 정확한 문장으로 통째로 대체된다.
   입력창 값에 이어 붙이기만 하면 "안녕 안녕하세 안녕하세요" 처럼 중간 단계가 전부 쌓인다. */

const RECOGNITION_LANGUAGE = "ko-KR";

// 사용자가 스스로 고칠 수 있는 오류만 안내한다 (그 외에는 오류 코드를 그대로 보여준다)
const ERROR_MESSAGE_BY_CODE = {
    "not-allowed"         : "⚠ 마이크 권한이 거부되었습니다.\n주소창의 자물쇠 아이콘에서 마이크를 허용한 뒤 다시 시도해주세요.",
    "service-not-allowed" : "⚠ 브라우저가 음성 인식 서비스를 차단했습니다.\n사이트 권한 설정에서 마이크를 허용해주세요.",
    "audio-capture"       : "⚠ 마이크를 찾을 수 없습니다.\n장치 연결 상태를 확인해주세요.",
    "network"             : "⚠ 네트워크 오류로 음성 인식에 실패했습니다.\n연결을 확인한 뒤 다시 시도해주세요."
};

export function useSTT({ onTranscriptChange, onError }) {
    // Chrome/Edge 는 webkit 접두사, 표준 이름은 아직 일부 브라우저에만 있다. Firefox 는 둘 다 없다.
    const isRecognitionSupported = typeof window !== "undefined"
        && ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);

    const [isRecording, setIsRecording] = useState(false);

    const recognitionRef       = useRef(null);
    const baseTextRef          = useRef("");     // 녹음 시작 시점의 입력창 내용
    const finalTranscriptRef   = useRef("");     // 확정된 인식 결과 누적본
    const isStoppingRef        = useRef(false);  // 사용자가 멈춘 것인지 (자동 재시작 여부를 가른다)

    // 콜백을 ref 로 들고 있는 이유 : 인식 객체의 이벤트 핸들러는 시작할 때 한 번만 붙는다.
    // 부모가 리렌더되어 콜백 참조가 바뀌어도 핸들러는 옛 것을 계속 잡고 있으므로 ref 로 최신값을 읽는다.
    const onTranscriptChangeRef = useRef(onTranscriptChange);
    const onErrorRef            = useRef(onError);

    useEffect(() => { onTranscriptChangeRef.current = onTranscriptChange; }, [onTranscriptChange]);
    useEffect(() => { onErrorRef.current            = onError;            }, [onError]);

    /* ── 정지 ── */

    const stopRecording = useCallback(() => {
        const recognition = recognitionRef.current;
        if (!recognition) return;
        isStoppingRef.current  = true;   // onend 에서 자동 재시작하지 않도록 먼저 세운다
        recognitionRef.current = null;
        setIsRecording(false);
        // abort() 가 아니라 stop() : 아직 확정되지 않은 마지막 말을 버리지 않고 받아 적고 끝낸다
        try { recognition.stop(); } catch (_ignored) {}
    }, []);

    /* ── 시작 ── */

    const startRecording = useCallback((baseText) => {
        if (!isRecognitionSupported || recognitionRef.current) return;

        const RecognitionConstructor = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition            = new RecognitionConstructor();
        recognition.lang            = RECOGNITION_LANGUAGE;
        recognition.continuous      = true;   // 한 문장이 끝나도 버튼을 다시 누를 때까지 계속 듣는다
        recognition.interimResults  = true;   // 말하는 도중에도 중간 결과를 입력창에 흘려보낸다
        recognition.maxAlternatives = 1;

        // 이미 적어둔 글이 있으면 그 뒤에 한 칸 띄우고 이어 붙인다 (지우지 않는다)
        baseTextRef.current        = baseText ? `${baseText.replace(/\s+$/, "")} ` : "";
        finalTranscriptRef.current = "";
        isStoppingRef.current      = false;

        recognition.onresult = (event) => {
            let interimTranscript = "";
            // resultIndex 부터가 이번에 갱신된 구간이다. 0 부터 훑으면 이미 더한 확정분을 또 더하게 된다.
            for (let resultIndex = event.resultIndex; resultIndex < event.results.length; resultIndex += 1) {
                const recognitionResult = event.results[resultIndex];
                const transcriptText    = recognitionResult[0].transcript;
                if (recognitionResult.isFinal) finalTranscriptRef.current += transcriptText;
                else                           interimTranscript          += transcriptText;
            }
            onTranscriptChangeRef.current(baseTextRef.current + finalTranscriptRef.current + interimTranscript);
        };

        recognition.onerror = (event) => {
            // no-speech(침묵) 와 aborted(우리가 멈춤) 는 정상 흐름의 일부라 조용히 넘긴다
            if (event.error === "no-speech" || event.error === "aborted") return;
            isStoppingRef.current  = true;   // 같은 오류로 무한 재시작하는 것을 막는다
            recognitionRef.current = null;
            setIsRecording(false);
            onErrorRef.current(ERROR_MESSAGE_BY_CODE[event.error] || `⚠ 음성 인식 오류 (${event.error})`);
        };

        recognition.onend = () => {
            // Chrome 은 continuous 여도 몇 초간 말이 없으면 스스로 세션을 끝낸다.
            // 사용자가 버튼으로 멈춘 게 아니라면 다시 시작해 "누를 때까지 듣는" 동작을 유지한다.
            if (isStoppingRef.current) return;
            try {
                recognition.start();
            } catch (_ignored) {
                recognitionRef.current = null;
                setIsRecording(false);
            }
        };

        try {
            recognition.start();
            recognitionRef.current = recognition;
            setIsRecording(true);
        } catch (_ignored) {
            // start() 는 이미 시작된 상태에서 InvalidStateError 를 던진다
            onErrorRef.current("⚠ 음성 인식을 시작하지 못했습니다. 잠시 후 다시 시도해주세요.");
        }
    }, [isRecognitionSupported]);

    /* ── 토글 ── */

    const toggleRecording = useCallback((baseText) => {
        if (recognitionRef.current) stopRecording();
        else                        startRecording(baseText);
    }, [startRecording, stopRecording]);

    // 언마운트(로그아웃·새로고침) 시 마이크를 놓는다 — 안 놓으면 탭의 녹음 표시가 남는다
    useEffect(() => () => {
        const recognition = recognitionRef.current;
        if (!recognition) return;
        isStoppingRef.current = true;
        try { recognition.abort(); } catch (_ignored) {}
    }, []);

    return { isRecognitionSupported, isRecording, toggleRecording, stopRecording };
}
