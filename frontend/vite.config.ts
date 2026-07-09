import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import tailwindcss from "@tailwindcss/vite";
import tsConfigPaths from "vite-tsconfig-paths";

// Converted from TanStack Start (SSR) to a plain client-side SPA.
// TanStack Router itself still works great in pure client mode - only the
// SSR wrapper (@tanstack/react-start / @lovable.dev/vite-tanstack-config /
// nitro) was removed, since this app has no server functions or SSR data
// loading, it only calls the FastAPI backend from the browser.
export default defineConfig({
  plugins: [
    tanstackRouter({ target: "react", autoCodeSplitting: true }),
    react(),
    tailwindcss(),
    tsConfigPaths(),
  ],
});
