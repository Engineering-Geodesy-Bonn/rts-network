import type { CheckStatus, JobStatus, JobType } from './types';

// ── Status ──────────────────────────────────────────────────────────────

export const STATUS_RANK: Record<CheckStatus, number> = { info: 0, ok: 1, unknown: 2, warn: 3, fail: 4 };

export const STATUS_LABEL: Record<CheckStatus, string> = {
    ok: 'OK',
    info: 'Info',
    unknown: 'Unverified',
    warn: 'Warning',
    fail: 'Problem',
};

export function worst(statuses: CheckStatus[]): CheckStatus {
    const relevant = statuses.filter((s) => s !== 'info');
    if (relevant.length === 0) return 'ok';
    return relevant.reduce((a, b) => (STATUS_RANK[b] > STATUS_RANK[a] ? b : a));
}

export const JOB_TYPE_LABEL: Record<JobType, string> = {
    test_connection: 'Beep test',
    track_prism: 'Tracking',
    change_face: 'Change face',
    dummy_tracking: 'Simulated tracking',
    turn_to_target: 'Turn to target',
    static_measurement: 'Static points (v1)',
    add_static_measurement: 'Static measurement',
    health_check: 'Instrument check',
};

export const JOB_STATUS_LABEL: Record<JobStatus, string> = {
    pending: 'Waiting',
    running: 'Running',
    lost: 'No contact',
    finished: 'Finished',
    failed: 'Failed',
    cancelled: 'Cancelled',
    interrupted: 'Interrupted',
};

export const JOB_STATUS_TONE: Record<JobStatus, CheckStatus> = {
    pending: 'info',
    running: 'ok',
    lost: 'fail',
    finished: 'unknown',
    failed: 'fail',
    cancelled: 'unknown',
    interrupted: 'warn',
};

// ── Numbers & time ──────────────────────────────────────────────────────

export function fmtTime(seconds: number | null | undefined): string {
    if (seconds == null || !isFinite(seconds)) return '–';
    const sign = seconds < 0 ? '−' : '';
    const v = Math.abs(seconds);
    if (v < 1e-3) return `${sign}${(v * 1e6).toFixed(1)} µs`;
    if (v < 1) return `${sign}${(v * 1e3).toFixed(2)} ms`;
    return `${sign}${v.toFixed(3)} s`;
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

/** Compact duration for tiles: 42 s · 3:07 · 1:02:03 */
export function fmtShortDuration(seconds: number | null | undefined): string {
    if (seconds == null || !isFinite(seconds)) return '–';
    const s = Math.max(0, Math.round(seconds));
    if (s < 60) return `${s} s`;
    const pad = (n: number) => String(n).padStart(2, '0');
    if (s < 3600) return `${Math.floor(s / 60)}:${pad(s % 60)}`;
    return `${Math.floor(s / 3600)}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
}

export function fmtClock(epochSeconds: number | null | undefined, withSeconds = true): string {
    if (epochSeconds == null) return '–';
    return new Date(epochSeconds * 1000).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: withSeconds ? '2-digit' : undefined,
    });
}

export function fmtDateTime(epochSeconds: number | null | undefined): string {
    if (epochSeconds == null) return '–';
    const date = new Date(epochSeconds * 1000);
    const today = new Date();
    const sameDay = date.toDateString() === today.toDateString();
    const time = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (sameDay) return `Today ${time}`;
    return `${date.toLocaleDateString([], { day: '2-digit', month: 'short', year: 'numeric' })} ${time}`;
}

export function fmtAgo(epochSeconds: number | null | undefined, now = Date.now() / 1000): string {
    if (epochSeconds == null) return 'never';
    return `${fmtDuration(now - epochSeconds)} ago`;
}

export function fmtCount(n: number | null | undefined): string {
    if (n == null) return '–';
    return n.toLocaleString();
}

export function fmtNumber(value: number | null | undefined, digits = 3): string {
    if (value == null || !isFinite(value)) return '–';
    return value.toFixed(digits);
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

// ── Units (the API uses SI: m, rad, s) ──────────────────────────────────

export const units = {
    radToGon: (rad: number) => (rad * 200) / Math.PI,
    gonToRad: (gon: number) => (gon * Math.PI) / 200,
    radToMgon: (rad: number) => (rad * 200000) / Math.PI,
    mgonToRad: (mgon: number) => (mgon * Math.PI) / 200000,
    sToMs: (s: number) => s * 1000,
    msToS: (ms: number) => ms / 1000,
    mToMm: (m: number) => m * 1000,
    mmToM: (mm: number) => mm / 1000,
};

// ── Instrument settings ─────────────────────────────────────────────────

export const PRISM_TYPES: Record<number, string> = {
    0: 'Leica round',
    1: 'Leica mini',
    2: 'Leica tape',
    3: 'Leica 360°',
    4: 'User defined 1',
    5: 'User defined 2',
    6: 'User defined 3',
    7: 'Leica 360° mini',
    8: 'Leica mini zero',
    9: 'User defined',
    10: 'Leica NDS tape',
    11: 'Leica GRZ121 round',
    12: 'Leica MPR122',
};

export const TMC_MEASUREMENT_MODES: Record<number, string> = { 1: 'Default distance', 2: 'Distance tracking' };
export const TMC_INCLINATION_MODES: Record<number, string> = { 0: 'Use sensor', 1: 'Automatic', 2: 'Use plane' };
export const EDM_MEASUREMENT_MODES: Record<number, string> = {
    6: 'Continuous standard',
    7: 'Continuous dynamic',
    8: 'Continuous reflectorless',
    9: 'Continuous fast',
};
export const FINE_ADJUST_POSITION_MODES: Record<number, string> = { 0: 'Normal', 1: 'Point' };

/** Intrinsic delays of the instrument models (s), from the intrinsic calibration */
export const INTERNAL_DELAYS: Record<string, number> = {
    MS60: 0.0,
    TS16: 7.22 / 1000,
    TS60: 4.98 / 1000,
};

// ── Colors for RTS in plots (distinguishable in light and dark) ─────────

export const RTS_COLORS = ['#2f7ef5', '#e8590c', '#2b9a3e', '#c2255c', '#7048e8', '#0c8599', '#b08800', '#5c7cfa'];

export function rtsColor(index: number): string {
    return RTS_COLORS[((index % RTS_COLORS.length) + RTS_COLORS.length) % RTS_COLORS.length];
}
