import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: "/static/lorebook/",
  plugins: [tailwindcss()],
  server: {
    origin: "http://localhost:5173",
    hmr: false,
  },
  input: "assets/js/app.ts",
  build: {
    manifest: "manifest.json",
  },
});
