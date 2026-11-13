import type { Job, JobSettings, JobStatus, JobType } from './types';

// ── Jobs ────────────────────────────────────────────────────────────────

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

const label = (labels: Record<number, string>, value: number) => labels[value] ?? `${value}`;

/** Prism the job was measured with ('–' if its settings were not recorded). */
export function jobPrism(job: Job): string {
    return job.settings ? label(PRISM_TYPES, job.settings.tracking.prism_type) : '–';
}

/** All settings of a job as label/value pairs, in field units. */
export function settingsRows(s: JobSettings): [string, string][] {
    const t = s.tracking;
    const gon = (rad: number) => `${units.radToGon(rad).toFixed(4)} gon`;
    const rows: [string, string][] = [
        ['Prism', label(PRISM_TYPES, t.prism_type)],
        ['Distance mode', label(EDM_MEASUREMENT_MODES, t.edm_measurement_mode)],
        ['Measurement mode', label(TMC_MEASUREMENT_MODES, t.tmc_measurement_mode)],
        ['Inclination', label(TMC_INCLINATION_MODES, t.tmc_inclination_mode)],
        ['Fine adjust mode', label(FINE_ADJUST_POSITION_MODES, t.fine_adjust_position_mode)],
        ['Search Hz / V', `${gon(t.fine_adjust_horizontal_search_range)} / ${gon(t.fine_adjust_vertical_search_range)}`],
        ['Power search', t.power_search ? `on, ${t.power_search_min_range}–${t.power_search_max_range} m` : 'off'],
    ];
    if (t.power_search) {
        rows.push(
            ['Search area center Hz / V', `${gon(t.power_search_area_dcenterhz)} / ${gon(t.power_search_area_dcenterv)}`],
            ['Search area size Hz / V', `${gon(t.power_search_area_drangehz)} / ${gon(t.power_search_area_drangev)}${t.power_search_area_enabled ? '' : ' (not restricted)'}`],
        );
    }
    rows.push(
        ['Station E / N / H', `${s.station_x.toFixed(3)} / ${s.station_y.toFixed(3)} / ${s.station_z.toFixed(3)} m`],
        ['Orientation', gon(s.orientation)],
        ['Delays internal / external', `${units.sToMs(s.internal_delay).toFixed(2)} / ${units.sToMs(s.external_delay).toFixed(2)} ms`],
        ['Distance σ', `${units.mToMm(s.distance_std_dev).toFixed(2)} mm + ${s.distance_ppm} ppm`],
        ['Angle σ', `${units.radToMgon(s.angle_std_dev).toFixed(2)} mgon`],
        ['Port', s.port.startsWith('bt://') || s.port.startsWith('sim://') ? s.port : `${s.port} · ${s.baudrate} baud, ${s.bytesize}${s.parity}${s.stopbits}`],
        ['Timeout', `${s.timeout} s`],
    );
    return rows;
}

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
