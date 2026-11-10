import { units } from './format';
import type { Columns } from './live.svelte';

/** Columns used for plotting */
export interface Plotted {
    t: number[];
    x: number[];
    y: number[];
    z: number[];
    d: number[];
    hz: number[];
    v: number[];
}

const KEYS = ['t', 'x', 'y', 'z', 'd', 'hz', 'v'] as const;

/** More points than a plot has pixels are never needed */
export const MAX_PLOT_POINTS = 2000;

/** Thins ranges of columns to at most `max` points (always keeping the last point). */
export function thin(sources: { cols: Columns | Plotted; from: number; to: number }[], max = MAX_PLOT_POINTS): Plotted {
    const total = sources.reduce((n, s) => n + Math.max(0, s.to - s.from), 0);
    const stride = Math.max(1, Math.ceil(total / max));
    const out: Plotted = { t: [], x: [], y: [], z: [], d: [], hz: [], v: [] };
    let k = 0;
    let last: { cols: Columns | Plotted; i: number } | null = null;
    for (const { cols, from, to } of sources) {
        for (let i = Math.max(0, from); i < to; i++, k++) {
            last = { cols, i };
            if (k % stride !== 0) continue;
            for (const key of KEYS) out[key].push(cols[key][i]);
        }
    }
    if (last && (k - 1) % stride !== 0) {
        for (const key of KEYS) out[key].push(last.cols[key][last.i]);
    }
    return out;
}

export type Quantity = 'z' | 'x' | 'y' | 'd' | 'hz' | 'v';

export const QUANTITIES: { value: Quantity; label: string; unit: string; scale?: (v: number) => number }[] = [
    { value: 'z', label: 'Height', unit: 'm' },
    { value: 'x', label: 'Easting', unit: 'm' },
    { value: 'y', label: 'Northing', unit: 'm' },
    { value: 'd', label: 'Slope distance', unit: 'm' },
    { value: 'hz', label: 'Horizontal angle', unit: 'gon', scale: units.radToGon },
    { value: 'v', label: 'Vertical angle', unit: 'gon', scale: units.radToGon },
];

export function loadPref<T>(key: string, fallback: T): T {
    try {
        const value = localStorage.getItem(key);
        return value === null ? fallback : (JSON.parse(value) as T);
    } catch {
        return fallback;
    }
}

export function savePref(key: string, value: unknown): void {
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch {
        /* storage not available */
    }
}
