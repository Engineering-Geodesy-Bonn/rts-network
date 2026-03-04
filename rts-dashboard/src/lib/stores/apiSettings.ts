import { writable } from 'svelte/store';

const DEFAULT_URL = '/api';

function createApiSettingsStore() {
    const stored = localStorage.getItem('rts-api-url');
    const { subscribe, set } = writable(stored || DEFAULT_URL);

    return {
        subscribe,
        set(url: string) {
            localStorage.setItem('rts-api-url', url);
            set(url);
        },
        reset() {
            localStorage.removeItem('rts-api-url');
            set(DEFAULT_URL);
        },
    };
}

export const apiUrl = createApiSettingsStore();
