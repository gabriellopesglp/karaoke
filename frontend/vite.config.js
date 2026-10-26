import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// Multi-página: index.html (TV, placeholder nesta fase) e remote.html (controle).
// O build vai direto para o diretório estático do backend.
export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: "../backend/karaoke/static",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        index: fileURLToPath(new URL("./index.html", import.meta.url)),
        remote: fileURLToPath(new URL("./remote.html", import.meta.url)),
      },
    },
  },
});
