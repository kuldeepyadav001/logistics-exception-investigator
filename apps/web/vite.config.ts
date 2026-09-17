import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev proxy: browser → /api → local FastAPI (blueprint: keep URLs relative,
// so the same build works when deployed behind API Gateway on AWS).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
