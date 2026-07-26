import { defineConfig } from "vite";
import react            from "@vitejs/plugin-react";

// 백엔드(src/server.py)는 CORS 를 allow_origins=["*"] 로 열어두므로 프록시 없이 절대 URL 로 직접 호출한다.
// 같은 오리진으로 묶고 싶으면 아래 server.proxy 주석을 풀고 .env 의 VITE_API_URL 을 "/api" 로 바꾼다.
export default defineConfig({
    plugins : [react()],
    server  : {
        port : 5173,
        open : true
        // proxy : {
        //     "/api" : { target : "http://localhost:8000", changeOrigin : true, rewrite : (path) => path.replace(/^\/api/, "") }
        // }
    },
    build : {
        outDir      : "dist",
        sourcemap   : true,
        chunkSizeWarningLimit : 900
    }
});
