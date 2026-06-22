import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 開発時は /api を FastAPI(uvicorn 既定 8000) にプロキシ。
// 本番はリバースプロキシ前提（gameApi.ts は相対 /api を叩く）。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
