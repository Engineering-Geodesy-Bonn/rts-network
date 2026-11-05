import type { CheckStatus } from './api/types';

export const STATUS_RANK: Record<CheckStatus, number> = {
    info: 0,
    ok: 1,
    unknown: 2,
    warn: 3,
    fail: 4,
};

export const STATUS_LABEL: Record<CheckStatus, string> = {
    ok: 'OK',
    info: 'Info',
    unknown: 'Unverified',
    warn: 'Warning',
    fail: 'Failure',
};

export const STATUS_ICON: Record<CheckStatus, string> = {
    ok: '✓',
    info: 'i',
    unknown: '?',
    warn: '!',
    fail: '✕',
};

/** Hex colors for SVG */
export const STATUS_HEX: Record<CheckStatus, string> = {
    ok: '#4ade80',
    info: '#60a5fa',
    unknown: '#94a3b8',
    warn: '#fbbf24',
    fail: '#f87171',
};

export const STATUS_TEXT: Record<CheckStatus, string> = {
    ok: 'text-green-400',
    info: 'text-blue-400',
    unknown: 'text-slate-400',
    warn: 'text-amber-400',
    fail: 'text-red-400',
};

export const STATUS_PILL: Record<CheckStatus, string> = {
    ok: 'bg-green-500/10 text-green-400 border-green-500/30',
    info: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    unknown: 'bg-slate-500/10 text-slate-300 border-slate-500/40',
    warn: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    fail: 'bg-red-500/10 text-red-400 border-red-500/30',
};

export const STATUS_BORDER: Record<CheckStatus, string> = {
    ok: 'border-green-500/40',
    info: 'border-blue-500/40',
    unknown: 'border-slate-500/60',
    warn: 'border-amber-500/50',
    fail: 'border-red-500/60',
};

export function worst(statuses: CheckStatus[]): CheckStatus {
    const relevant = statuses.filter((s) => s !== 'info');
    if (relevant.length === 0) return 'ok';
    return relevant.reduce((a, b) => (STATUS_RANK[b] > STATUS_RANK[a] ? b : a));
}

/** Seconds → µs / ms / s with sign */
export function fmtTime(seconds: number | null | undefined): string {
    if (seconds == null || !isFinite(seconds)) return '–';
    const sign = seconds < 0 ? '−' : '';
    const v = Math.abs(seconds);
    if (v < 1e-3) return `${sign}${(v * 1e6).toFixed(1)} µs`;
    if (v < 1) return `${sign}${(v * 1e3).toFixed(2)} ms`;
    return `${sign}${v.toFixed(3)} s`;
}

export function fmtSignedTime(seconds: number | null | undefined): string {
    if (seconds == null) return '–';
    return (seconds >= 0 ? '+' : '') + fmtTime(seconds);
}

export function fmtDuration(seconds: number | null | undefined): string {
    if (seconds == null || !isFinite(seconds)) return '–';
    const s = Math.max(0, seconds);
    if (s < 10) return `${s.toFixed(1)} s`;
    if (s < 60) return `${Math.round(s)} s`;
    if (s < 3600) return `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`;
    if (s < 86400) return `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min`;
    return `${Math.floor(s / 86400)} d ${Math.floor((s % 86400) / 3600)} h`;
}

export function fmtBytes(value: number | null | undefined): string {
    if (value == null) return '–';
    const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
    let v = value;
    let i = 0;
    while (v >= 1024 && i < units.length - 1) {
        v /= 1024;
        i++;
    }
    return `${v.toFixed(1)} ${units[i]}`;
}

export function fmtNumber(value: number | null | undefined, digits = 2, unit = ''): string {
    if (value == null || !isFinite(value)) return '–';
    return `${value.toFixed(digits)}${unit ? ' ' + unit : ''}`;
}

export const GPS_MODES: Record<number, string> = {
    0: 'Unknown',
    1: 'No fix',
    2: '2D fix',
    3: '3D fix',
};

export const CHRONY_STATES: Record<string, string> = {
    '*': 'selected',
    '+': 'combined',
    '-': 'not combined',
    x: 'falseticker',
    '~': 'too variable',
    '?': 'unusable',
};

export const CHRONY_MODES: Record<string, string> = {
    '#': 'refclock',
    '^': 'server',
    '=': 'peer',
};
