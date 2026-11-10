export type Theme = 'system' | 'light' | 'dark';

function load(): Theme {
    try {
        const value = localStorage.getItem('rts-theme');
        return value === 'light' || value === 'dark' ? value : 'system';
    } catch {
        return 'system';
    }
}

class ThemeStore {
    theme = $state<Theme>(load());
    /** Incremented when the effective colors change (plots re-read the CSS variables) */
    version = $state(0);

    constructor() {
        this.apply();
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => this.version++);
    }

    set(theme: Theme): void {
        this.theme = theme;
        try {
            if (theme === 'system') localStorage.removeItem('rts-theme');
            else localStorage.setItem('rts-theme', theme);
        } catch {
            /* storage not available */
        }
        this.apply();
    }

    private apply(): void {
        if (this.theme === 'system') document.documentElement.removeAttribute('data-theme');
        else document.documentElement.setAttribute('data-theme', this.theme);
        const meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.setAttribute('content', getComputedStyle(document.documentElement).getPropertyValue('--surface').trim());
        this.version++;
    }
}

export const theme = new ThemeStore();

export function cssVar(name: string): string {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
