// ── Prism Types ─────────────────────────────────────────────
export const PRISM_TYPES: Record<number, string> = {
    0: 'Leica Round',
    1: 'Leica Mini',
    2: 'Leica Tape',
    3: 'Leica 360',
    4: 'User Defined 1',
    5: 'User Defined 2',
    6: 'User Defined 3',
    7: 'Leica 360 Mini',
    8: 'Leica Mini Zero',
    9: 'User Defined',
    10: 'Leica NDS Tape',
    11: 'Leica GRZ121 Round',
    12: 'Leica MPR122',
};

// ── TMC Measurement Modes ───────────────────────────────────
export const TMC_MEASUREMENT_MODES: Record<number, string> = {
    1: 'Default Distance',
    2: 'Distance Tracking',
};

// ── TMC Inclination Modes ───────────────────────────────────
export const TMC_INCLINATION_MODES: Record<number, string> = {
    0: 'Use Sensor',
    1: 'Automatic',
    2: 'Use Plane',
};

// ── EDM Measurement Modes ───────────────────────────────────
export const EDM_MEASUREMENT_MODES: Record<number, string> = {
    6: 'Continuous Standard',
    7: 'Continuous Dynamic',
    8: 'Continuous Reflectorless',
    9: 'Continuous Fast',
};

// ── Fine Adjust Position Modes ──────────────────────────────
export const FINE_ADJUST_POSITION_MODES: Record<number, string> = {
    0: 'Norm',
    1: 'Point',
};

// ── Serial Parity ───────────────────────────────────────────
export const PARITY_OPTIONS: Record<string, string> = {
    N: 'None',
    E: 'Even',
    O: 'Odd',
};

// ── Job Types ───────────────────────────────────────────────
export const JOB_TYPE_NAMES: Record<string, string> = {
    test_connection: 'Test Connection',
    track_prism: 'Track Prism',
    change_face: 'Change Face',
    dummy_tracking: 'Dummy Tracking',
    turn_to_target: 'Turn to Target',
    static_measurement: 'Static Measurement',
};

// ── Job Status Colors ───────────────────────────────────────
export const JOB_STATUS_COLORS: Record<string, string> = {
    pending: 'text-yellow-400',
    running: 'text-blue-400',
    finished: 'text-green-400',
    failed: 'text-red-400',
};

export const JOB_STATUS_BG_COLORS: Record<string, string> = {
    pending: 'bg-yellow-500/10 border-yellow-500/30',
    running: 'bg-blue-500/10 border-blue-500/30',
    finished: 'bg-green-500/10 border-green-500/30',
    failed: 'bg-red-500/10 border-red-500/30',
};

// ── Unit Conversions ────────────────────────────────────────
export const units = {
    msToS: (ms: number) => ms / 1000,
    sToMs: (s: number) => s * 1000,
    mmToM: (mm: number) => mm / 1000,
    mToMm: (m: number) => m * 1000,
    mgonToRad: (mgon: number) => ((mgon / 1000) * Math.PI) / 200,
    radToMgon: (rad: number) => ((rad * 200) / Math.PI) * 1000,
    gonToRad: (gon: number) => (gon * Math.PI) / 200,
    radToGon: (rad: number) => (rad * 200) / Math.PI,
};

// ── Polling Intervals ───────────────────────────────────────
export const RTS_STATUS_POLL_MS = 1000;
