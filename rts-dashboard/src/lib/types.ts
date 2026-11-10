export type JobType =
    | 'test_connection'
    | 'track_prism'
    | 'change_face'
    | 'dummy_tracking'
    | 'turn_to_target'
    | 'static_measurement'
    | 'add_static_measurement'
    | 'health_check';

export type JobStatus = 'pending' | 'running' | 'lost' | 'finished' | 'failed' | 'cancelled' | 'interrupted';

export const ACTIVE_STATUSES: JobStatus[] = ['pending', 'running', 'lost'];
export const MEASURING_TYPES: JobType[] = ['track_prism', 'dummy_tracking', 'static_measurement', 'add_static_measurement'];
export const TRACKING_TYPES: JobType[] = ['track_prism', 'dummy_tracking'];

export interface Session {
    id: string;
    name: string;
    notes: string;
    created_at: number;
    archived: boolean;
    rts_count: number;
    job_count: number;
    measurement_count: number;
    last_activity: number | null;
}

export interface Device {
    id: string;
    ip: string;
    hostname: string | null;
    name: string | null;
    created_at: number;
    last_seen: number | null;
}

export interface TrackingSettings {
    tmc_measurement_mode: number;
    tmc_inclination_mode: number;
    edm_measurement_mode: number;
    prism_type: number;
    fine_adjust_position_mode: number;
    fine_adjust_horizontal_search_range: number;
    fine_adjust_vertical_search_range: number;
    power_search_area_dcenterhz: number;
    power_search_area_dcenterv: number;
    power_search_area_drangehz: number;
    power_search_area_drangev: number;
    power_search_area_enabled: number;
    power_search_min_range: number;
    power_search_max_range: number;
    power_search: boolean;
}

export interface RTSConfig {
    name: string;
    port: string;
    baudrate: number;
    timeout: number;
    parity: string;
    stopbits: number;
    bytesize: number;
    internal_delay: number;
    external_delay: number;
    station_x: number;
    station_y: number;
    station_z: number;
    orientation: number;
    distance_std_dev: number;
    angle_std_dev: number;
    distance_ppm: number;
}

export interface InstrumentReport {
    ok: boolean;
    source: string;
    errors: string[];
    collected_at: number | null;
    instrument_name: string | null;
    serial_number: number | null;
    software_version: string | null;
    battery_capacity: number | null;
    power_source: string | null;
    internal_temperature: number | null;
    face: number | null;
    latency_mean: number | null;
    latency_max: number | null;
    received_at: number;
}

export interface RTS extends RTSConfig {
    id: string;
    session_id: string;
    device_id: string | null;
    tracking: TrackingSettings;
    instrument_report: InstrumentReport | null;
    created_at: number;
    deleted: boolean;
}

export interface Job {
    id: string;
    rts_id: string;
    type: JobType;
    status: JobStatus;
    payload: Record<string, unknown>;
    created_at: number;
    started_at: number | null;
    finished_at: number | null;
    worker_id: string | null;
    stop_requested: boolean;
    error: string | null;
    note: string;
    count: number;
    first_t: number | null;
    last_t: number | null;
    last_rx: number | null;
}

export interface JobPage {
    items: Job[];
    next_before: number | null;
}

export interface MeasurementSeries {
    job_id: string;
    rts_id: string;
    total: number;
    stride: number;
    seq: number[];
    t: number[];
    ts: number[];
    d: number[];
    hz: number[];
    v: number[];
    x: number[];
    y: number[];
    z: number[];
    ok: boolean[];
}

export interface Problem {
    severity: 'error' | 'warning';
    subject: string;
    message: string;
    rts_id: string | null;
    device_id: string | null;
}

export interface StationHealth {
    rts_id: string;
    state: 'idle' | 'waiting' | 'measuring' | 'busy' | 'no_contact';
    job_id: string | null;
    rate_hz: number | null;
    last_data_age: number | null;
    battery: number | null;
}

export interface DeviceHealth {
    device_id: string;
    name: string;
    ip: string;
    online: boolean;
    last_seen_age: number | null;
    time_sync: 'gnss' | 'network' | 'none' | 'unknown';
    time_error: number | null;
    cpu_temperature: number | null;
    disk_free: number | null;
    unsent: number;
}

export interface Health {
    session_id: string | null;
    server_time: number;
    problems: Problem[];
    stations: StationHealth[];
    devices: DeviceHealth[];
}

export interface ExternalSensor {
    id: string;
    ip: string;
    name: string;
    logging_active: boolean;
    created_at: number;
    last_seen: number | null;
    count: number;
}

export interface SensorRoles {
    primary_sensor_id: string | null;
    secondary_sensor_id: string | null;
}

export interface SynchronizerState extends SensorRoles {
    delta_t: number;
    bias: number;
    sigma_delta_t: number;
    sigma_bias: number;
}

export interface ServerInfo {
    version: string;
    server_time: number;
    started_at: number;
    db_path: string;
    db_size: number;
    schema_version: number;
    writer: Record<string, number>;
    event_clients: number;
    legacy_import: {
        source?: string;
        ok?: boolean;
        counts?: Record<string, number>;
        jobs_verified?: number;
        problems?: string[];
        duration?: number;
        started_at?: number;
    } | null;
}

/** Messages of the /events websocket */
export interface LiveMessage {
    type: 'live';
    job_id: string;
    rts_id: string;
    session_id: string | null;
    count: number;
    seq: number[];
    t: number[];
    d: number[];
    hz: number[];
    v: number[];
    x: number[];
    y: number[];
    z: number[];
    ok: boolean[];
}

export type ServerEvent =
    | { type: 'hello'; server_time: number; version: string }
    | { type: 'tick'; server_time: number }
    | { type: 'pong'; server_time: number }
    | { type: 'health'; health: Health }
    | LiveMessage
    | { type: 'job'; job: Job }
    | { type: 'job_deleted'; job_id: string; rts_id: string }
    | { type: 'changed'; entity: string; id: string | null; session_id: string | null };
