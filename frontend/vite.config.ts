import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// KisanOS frontend dev server: port 5173 (PRD), proxying /api to the local
// backend so the app is same-origin in development (no CORS needed for the
// app itself; the backend additionally allows http://localhost:5173).
//
// Default target is http://localhost:8000. Override for local verification
// against a backend on another port:
//   VITE_API_PROXY_TARGET=http://localhost:8001 npm run dev
const proxyTarget =
  process.env.VITE_API_PROXY_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 5173,
    strictPort: true,
  },
});
