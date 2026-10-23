import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy to FastAPI so dev uses the same-origin URLs production uses.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
});
