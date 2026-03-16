import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../h5web_dist",
    emptyOutDir: true,
  },
  base: "/",
});
