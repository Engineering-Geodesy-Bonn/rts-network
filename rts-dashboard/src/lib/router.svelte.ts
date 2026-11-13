/** Minimal hash router: #/  ·  #/s/<session>/<page>[/<id>]  ·  #/settings */

export type Page = 'measure' | 'plot' | 'data' | 'sensors' | 'setup';

export interface Route {
    name: 'sessions' | 'session' | 'settings';
    sessionId: string | null;
    page: Page;
    id: string | null;
}

const PAGES: Page[] = ['measure', 'plot', 'data', 'sensors', 'setup'];

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

// The page before the settings, for their Back link (history.back() does nothing when the
// settings were opened directly, e.g. after a reload or from a bookmark)
let current = location.hash;
let beforeSettings = '#/';

window.addEventListener('hashchange', () => {
    if (parse(current).name !== 'settings') beforeSettings = current || '#/';
    current = location.hash;
    router.route = parse(location.hash);
});

export function backFromSettings(): string {
    return beforeSettings;
}

export function href(sessionId: string | null, page?: Page, id?: string | null): string {
    if (!sessionId) return '#/';
    return `#/s/${encodeURIComponent(sessionId)}/${page ?? 'measure'}${id ? '/' + encodeURIComponent(id) : ''}`;
}

export function navigate(target: string): void {
    if (location.hash !== target) location.hash = target;
}
