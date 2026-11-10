import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';

// The API is proxied under /api (as nginx does in production), including the websockets.
const target = process.env.API_TARGET ?? 'http://localhost:8000';
const proxy = {
    '/api': {
        target,
        changeOrigin: true,
        ws: true,
        rewrite: (path: string) => path.replace(/^\/api/, ''),
    },
};

export default defineConfig({
    plugins: [tailwindcss(), svelte()],
    server: { proxy },
    preview: { proxy },
});
