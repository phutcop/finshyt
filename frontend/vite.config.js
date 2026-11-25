import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: process.env.GITHUB_PAGES === "true" ? "/finshyt/" : "/",
  build: {
    outDir: "dist",
    assetsDir: "assets",
    sourcemap: false,
    emptyOutDir: true,
  },
  server: {
    port: 5174,
    strictPort: true,
    open: false,
    proxy: {
      "/api": "http://127.0.0.1:8001",
      "/chat": "http://127.0.0.1:8001",
    },
  },
  preview: {
    port: 4173,
  },
});
