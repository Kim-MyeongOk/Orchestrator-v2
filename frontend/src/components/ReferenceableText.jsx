import { createPortal } from "react-dom";
import { useCallback }  from "react";
import { useEffect }    from "react";
import { useRef }       from "react";
import { useState }     from "react";

/* 답변 본문에서 드래그(또는 선택 후 우클릭)한 구간을 질문 문맥으로 담아가는 「참조하기」 팝업.

   팝업을 body 포털로 띄우는 이유 : 말풍선 조상에 overflow·transform(말풍선 등장 애니메이션)이 걸려 있어
   내부에 그리면 잘리거나 fixed 좌표 기준이 말풍선으로 바뀐다. */

const REFERENCE_MAXIMUM_LENGTH    = 2000;   // 서버(ServerApplication.REFERENCED_TEXT_MAXIMUM_LENGTH)와 맞춘 값
const POPUP_HALF_WIDTH_PIXEL      = 48;     // 화면 밖으로 나가지 않게 가두기 위한 대략치
const VIEWPORT_EDGE_MARGIN_PIXEL  = 8;

export default function ReferenceableText({ onQuote, children }) {
    const containerRef = useRef(null);
    const popupRef     = useRef(null);

    const [popupState, setPopupState] = useState(null);   // { x, y, text }

    const closePopup = useCallback(() => setPopupState(null), []);

    // 선택 구간이 이 말풍선 안에 온전히 들어 있을 때만 발췌로 인정한다
    // (말풍선 밖까지 걸친 드래그는 다른 메시지 내용이 섞이므로 참조 대상이 아니다)
    const readSelectionText = useCallback(() => {
        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return "";
        const containerElement = containerRef.current;
        if (!containerElement) return "";
        if (!containerElement.contains(selection.anchorNode) || !containerElement.contains(selection.focusNode)) return "";
        return selection.toString().trim();
    }, []);

    const openPopupAt = useCallback((clientX, clientY, selectedText) => {
        const minimumX = POPUP_HALF_WIDTH_PIXEL + VIEWPORT_EDGE_MARGIN_PIXEL;
        const maximumX = window.innerWidth - POPUP_HALF_WIDTH_PIXEL - VIEWPORT_EDGE_MARGIN_PIXEL;
        setPopupState({
            x    : Math.min(Math.max(clientX, minimumX), maximumX),
            y    : Math.max(clientY, 44),   // 화면 상단으로 잘리지 않게 최소 높이를 둔다
            text : selectedText.slice(0, REFERENCE_MAXIMUM_LENGTH)
        });
    }, []);

    const onMouseUp = useCallback(() => {
        // 드래그 종료 : 브라우저가 선택을 확정한 뒤에 읽어야 하므로 한 틱 미룬다
        setTimeout(() => {
            const selectedText = readSelectionText();
            if (!selectedText) { closePopup(); return; }
            const selectionRect = window.getSelection().getRangeAt(0).getBoundingClientRect();
            openPopupAt(selectionRect.left + selectionRect.width / 2, selectionRect.top - 10, selectedText);
        }, 0);
    }, [closePopup, openPopupAt, readSelectionText]);

    const onContextMenu = useCallback((event) => {
        // 선택 구간이 있을 때만 브라우저 기본 메뉴를 가로챈다.
        // 선택 없이 누른 우클릭까지 막으면 새로고침·검사 같은 평소 동작을 빼앗게 된다.
        const selectedText = readSelectionText();
        if (!selectedText) return;
        event.preventDefault();
        openPopupAt(event.clientX, event.clientY - 10, selectedText);
    }, [openPopupAt, readSelectionText]);

    // 팝업 닫기 : 바깥 클릭 · Esc · 스크롤 · 리사이즈
    useEffect(() => {
        if (!popupState) return;

        const onDocumentMouseDown = (event) => {
            if (popupRef.current && popupRef.current.contains(event.target)) return;
            closePopup();
        };
        const onDocumentKeyDown = (event) => { if (event.key === "Escape") closePopup(); };

        document.addEventListener("mousedown", onDocumentMouseDown);
        document.addEventListener("keydown", onDocumentKeyDown);
        // 스크롤은 캡처 단계로 받는다 (대화창 내부 스크롤도 잡기 위함) — 좌표가 어긋나므로 따라가지 않고 닫는다
        window.addEventListener("scroll", closePopup, true);
        window.addEventListener("resize", closePopup);

        return () => {
            document.removeEventListener("mousedown", onDocumentMouseDown);
            document.removeEventListener("keydown", onDocumentKeyDown);
            window.removeEventListener("scroll", closePopup, true);
            window.removeEventListener("resize", closePopup);
        };
    }, [popupState, closePopup]);

    const onQuoteClick = () => {
        onQuote(popupState.text);
        window.getSelection()?.removeAllRanges();   // 담은 뒤에는 선택 하이라이트를 걷어낸다
        closePopup();
    };

    return (
        <div ref={containerRef} onMouseUp={onMouseUp} onContextMenu={onContextMenu}>
            {children}

            {popupState ? createPortal(
                <div ref={popupRef} role="dialog" aria-label="선택 텍스트 참조"
                     style={{ position : "fixed", left : `${popupState.x}px`, top : `${popupState.y}px`, transform : "translate(-50%, -100%)", zIndex : 60 }}>
                    {/* mousedown 기본동작을 막아 선택이 풀리지 않게 한다 (풀리면 click 시점에 발췌를 잃는다) */}
                    <button type="button" onMouseDown={(event) => event.preventDefault()} onClick={onQuoteClick}
                            className="px-2.5 py-1.5 rounded-lg bg-slate-800 dark:bg-slate-700 text-white text-[11px] font-medium whitespace-nowrap shadow-lg ring-1 ring-black/10 hover:bg-slate-700 dark:hover:bg-slate-600 transition">
                        ❝ 참조하기
                    </button>
                </div>,
                document.body
            ) : null}
        </div>
    );
}
