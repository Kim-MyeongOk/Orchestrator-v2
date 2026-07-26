import { useCallback } from "react";
import { useRef }      from "react";
import { useState }    from "react";

const TOAST_VISIBLE_MS = 6000;

export function useToast() {
    const [toastList, setToastList] = useState([]);   // [{ toastId, text, toneClass }]
    const toastSequenceRef          = useRef(0);

    const showToast = useCallback((text, toneClass = "bg-red-600/95") => {
        const toastId = ++toastSequenceRef.current;
        setToastList(previousList => [...previousList, { toastId, text, toneClass }]);
        setTimeout(() => {
            setToastList(previousList => previousList.filter(toast => toast.toastId !== toastId));
        }, TOAST_VISIBLE_MS);
    }, []);

    const dismissToast = useCallback((toastId) => {
        setToastList(previousList => previousList.filter(toast => toast.toastId !== toastId));
    }, []);

    return { toastList, showToast, dismissToast };
}
