import { writable } from 'svelte/store';
import type { SessionResponse } from '../api/types';

function createSessionStore() {
    const stored = localStorage.getItem('rts-session');
    const initial: SessionResponse | null = stored ? JSON.parse(stored) : null;
    const { subscribe, set } = writable<SessionResponse | null>(initial);

    return {
        subscribe,
        select(session: SessionResponse) {
            localStorage.setItem('rts-session', JSON.stringify(session));
            set(session);
        },
        clear() {
            localStorage.removeItem('rts-session');
            set(null);
        },
    };
}

export const currentSession = createSessionStore();
