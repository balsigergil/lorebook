import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: "/static/lorebook/",
  plugins: [react(), tailwindcss()],
  server: {
    origin: "http://localhost:5173",
    cors: true,
    hmr: false,
  },
  build: {
    manifest: "manifest.json",
    chunkSizeWarningLimit: 800,
    outDir: "dist",
    rollupOptions: {
      input: ["assets/js/app.ts", "assets/editor/main.tsx"],
    },
  },
});
