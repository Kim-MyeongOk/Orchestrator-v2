import { useCallback } from "react";
import { useEffect }   from "react";
import { useState }    from "react";

import { THEME_STORAGE_KEY } from "../constants/storageKeys";

export function useTheme() {
    // 초기값은 index.html 의 FOUC 방지 스크립트가 이미 html 태그에 적용해 둔 상태를 그대로 읽는다
    const [isDarkTheme, setIsDarkTheme] = useState(() => document.documentElement.classList.contains("dark"));

    const toggleTheme = useCallback(() => {
        setIsDarkTheme(previousIsDark => {
            const nextIsDark = !previousIsDark;
            document.documentElement.classList.toggle("dark", nextIsDark);
            localStorage.setItem(THEME_STORAGE_KEY, nextIsDark ? "dark" : "light");
            return nextIsDark;
        });
    }, []);

    useEffect(() => {
        // 시스템 테마 변경 실시간 반영 (사용자가 직접 고르기 전까지만)
        const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
        const onSystemThemeChanged = (event) => {
            if (localStorage.getItem(THEME_STORAGE_KEY)) return;   // 명시적 선택이 있으면 시스템 변경 무시
            document.documentElement.classList.toggle("dark", event.matches);
            setIsDarkTheme(event.matches);
        };
        mediaQuery.addEventListener("change", onSystemThemeChanged);
        return () => mediaQuery.removeEventListener("change", onSystemThemeChanged);
    }, []);

    return { isDarkTheme, toggleTheme };
}
