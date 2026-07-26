import { StrictMode }  from "react";
import { createRoot }   from "react-dom/client";

import App from "./App";

import { AUTH_USER_ID_STORAGE_KEY } from "./constants/storageKeys";
import { LOGIN_PAGE_PATH }          from "./constants/storageKeys";

import "./index.css";

/* 인증 게이트 : 로그인 정보가 없으면 앱을 마운트하지 않고 로그인 페이지로 보낸다.
   이게 없으면 토큰 없이 방 목록 API 를 두드려 401 이 쌓이고, 실패 폴백으로 빈 방까지 생성된다. */
if (!localStorage.getItem(AUTH_USER_ID_STORAGE_KEY)) {
    location.replace(LOGIN_PAGE_PATH);
} else {
    createRoot(document.getElementById("root")).render(
        <StrictMode>
            <App />
        </StrictMode>
    );
}
