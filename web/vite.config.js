import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  // Absoluta (no "./"): con vue-router en modo history, el navegador puede pedir directo
  // /documentos/<codigo> (refresh o link compartido) -- el backend sirve index.html como
  // fallback (doctyp_web.py: _estaticos), pero con base relativa esas referencias a assets
  // se resolverían contra /documentos/assets/... en vez de /assets/... (404).
  base: "/",
  build: {
    outDir: "dist",
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8787",
    },
  },
});
