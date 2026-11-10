/** Minimal hash router: #/  ·  #/s/<session>/<page>[/<id>]  ·  #/settings */

export type Page = 'measure' | 'data' | 'setup';

export interface Route {
    name: 'sessions' | 'session' | 'settings';
    sessionId: string | null;
    page: Page;
    id: string | null;
}

const PAGES: Page[] = ['measure', 'data', 'setup'];

function parse(hash: string): Route {
    const parts = hash.replace(/^#\/?/, '').split('/').filter(Boolean).map(decodeURIComponent);
    if (parts[0] === 's' && parts[1]) {
        const page = (PAGES.includes(parts[2] as Page) ? parts[2] : 'measure') as Page;
        return { name: 'session', sessionId: parts[1], page, id: parts[3] ?? null };
    }
    if (parts[0] === 'settings') return { name: 'settings', sessionId: null, page: 'measure', id: null };
    return { name: 'sessions', sessionId: null, page: 'measure', id: null };
}

export const router = $state({ route: parse(location.hash) });

window.addEventListener('hashchange', () => {
    router.route = parse(location.hash);
});

export function href(sessionId: string | null, page?: Page, id?: string | null): string {
    if (!sessionId) return '#/';
    return `#/s/${encodeURIComponent(sessionId)}/${page ?? 'measure'}${id ? '/' + encodeURIComponent(id) : ''}`;
}

export function navigate(target: string): void {
    if (location.hash !== target) location.hash = target;
}
