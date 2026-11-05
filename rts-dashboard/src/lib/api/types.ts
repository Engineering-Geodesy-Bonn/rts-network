// === Session ===
export interface SessionResponse {
    id: string;
    name: string;
    created_at: number;
}

export interface CreateSessionRequest {
    name: string;
}

// === RTS ===
export interface RTSResponse {
    id: string;
    device_id: string;
    name: string;
    baudrate: number;
    port: string;
    timeout: number;
    parity: string;
    stopbits: number;
    bytesize: number;
    external_delay: number;
    internal_delay: number;
    station_x: number;
    station_y: number;
    station_z: number;
    orientation: number;
    distance_std_dev: number;
    angle_std_dev: number;
    distance_ppm: number;
}

export interface CreateRTSRequest {
    name?: string;
    baudrate?: number;
    port?: string;
    timeout?: number;
    parity?: string;
    stopbits?: number;
    bytesize?: number;
    external_delay?: number;
    internal_delay?: number;
    station_x?: number;
    station_y?: number;
    station_z?: number;
    orientation?: number;
    distance_std_dev?: number;
    angle_std_dev?: number;
    distance_ppm?: number;
    device_id: string;
    session_id: string;
}

export interface UpdateRTSRequest {
    name?: string;
    baudrate?: number;
    port?: string;
    timeout?: number;
    parity?: string;
    stopbits?: number;
    bytesize?: number;
    external_delay?: number;
    internal_delay?: number;
    station_x?: number;
    station_y?: number;
    station_z?: number;
    orientation?: number;
    distance_std_dev?: number;
    angle_std_dev?: number;
    distance_ppm?: number;
}

// === Tracking Settings ===
export interface TrackingSettingsResponse {
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
    rts_id: string;
    id: string;
}

export interface UpdateTrackingSettingsRequest {
    tmc_measurement_mode?: number;
    tmc_inclination_mode?: number;
    edm_measurement_mode?: number;
    prism_type?: number;
    fine_adjust_position_mode?: number;
    fine_adjust_horizontal_search_range?: number;
    fine_adjust_vertical_search_range?: number;
    power_search_area_dcenterhz?: number;
    power_search_area_dcenterv?: number;
    power_search_area_drangehz?: number;
    power_search_area_drangev?: number;
    power_search_area_enabled?: number;
    power_search_min_range?: number;
    power_search_max_range?: number;
    power_search?: boolean;
}

// === Measurements ===
export interface MeasurementResponse {
    controller_timestamp: number;
    sensor_timestamp: number;
    response_length: number;
    geocom_return_code: number;
    rpc_return_code: number;
    distance: number;
    horizontal_angle: number;
    vertical_angle: number;
    rts_job_id: string;
    rts_id: string | null;
}

// === RTS Jobs ===
export type RTSJobStatus = 'pending' | 'running' | 'finished' | 'failed';

export type RTSJobType =
    | 'test_connection'
    | 'track_prism'
    | 'change_face'
    | 'dummy_tracking'
    | 'turn_to_target'
    | 'static_measurement'
    | 'add_static_measurement'
    | 'health_check';

export interface RTSJobResponse {
    job_id: string;
    rts_id: string | null;
    job_type: RTSJobType;
    job_status: RTSJobStatus;
    created_at: number;
    finished_at: number | null;
    duration: number | null;
    num_measurements: number | null;
    datarate: number | null;
    payload: Record<string, unknown>;
}

export interface CreateRTSJobRequest {
    rts_id: string;
    job_type: RTSJobType;
    payload?: Record<string, unknown>;
}

// === Devices ===
export interface DeviceResponse {
    ip: string;
    last_seen: number;
    id: string;
}

// === External Sensors ===
export interface ExternalSensorResponse {
    id: string;
    name: string;
    last_seen: number;
    ip: string;
    logging_active: boolean;
}

// === RTS Status ===
export interface RTSStatusResponse {
    job_id: string | null;
    busy: boolean;
    last_measurement: MeasurementResponse | null;
    num_measurements: number;
    datarate: number;
}

// === Synchronizer ===
export interface SensorRolesResponse {
    primary_sensor_id: string | null;
    secondary_sensor_id: string | null;
}

export interface SynchronizerStateResponse {
    delta_t: number;
    bias: number;
    sigma_delta_t: number;
    sigma_bias: number;
}

// === Target ===
export interface TargetPosition {
    x: number;
    y: number;
    z: number;
    timestamp: number;
    rts_id: string | null;
}

// === Status Board ===
export type CheckStatus = 'ok' | 'info' | 'unknown' | 'warn' | 'fail';

export interface StatusCheck {
    key: string;
    label: string;
    status: CheckStatus;
    message: string;
}

export interface ChronyTracking {
    reference_id: string;
    reference_name: string;
    stratum: number;
    ref_time: number;
    system_time_offset: number;
    last_offset: number;
    rms_offset: number;
    frequency_ppm: number;
    residual_freq_ppm: number;
    skew_ppm: number;
    root_delay: number;
    root_dispersion: number;
    update_interval: number;
    leap_status: string;
}

export interface ChronySource {
    mode: string;
    state: string;
    name: string;
    stratum: number;
    poll: number;
    reach: number;
    last_rx: number | null;
    offset: number;
    measured_offset: number;
    error: number;
}

export interface ChronyStatus {
    available: boolean;
    error: string | null;
    tracking: ChronyTracking | null;
    sources: ChronySource[];
}

export interface GpsStatus {
    available: boolean;
    error: string | null;
    devices: { path: string | null; driver: string | null }[];
    mode: number | null;
    status: number | null;
    time: string | null;
    lat: number | null;
    lon: number | null;
    alt: number | null;
    eph: number | null;
    epv: number | null;
    ept: number | null;
    satellites_visible: number | null;
    satellites_used: number | null;
    hdop: number | null;
    pdop: number | null;
    tdop: number | null;
}

export interface SystemInfo {
    hostname: string | null;
    platform: string | null;
    python_version: string | null;
    uptime: number | null;
    cpu_count: number | null;
    cpu_temperature: number | null;
    load_average: number[];
    memory_total: number | null;
    memory_available: number | null;
    disk_total: number | null;
    disk_free: number | null;
    undervoltage: boolean | null;
    serial_ports: { path: string; target: string }[];
    pps_devices: string[];
}

export interface WorkerRuntime {
    state: string;
    job_id: string | null;
    job_type: string | null;
    rts_id: string | null;
    job_started_at: number | null;
    last_activity_at: number | null;
    jobs_finished: number;
    jobs_failed: number;
    last_error: string | null;
    last_error_at: number | null;
    streaming: boolean;
    stream_connected: boolean;
    stream_backlog: number;
    measurements_logged: number;
    measurements_sent: number;
    last_measurement_at: number | null;
}

export interface ClockSample {
    offset: number;
    delay: number;
    measured_at: number;
    samples: number;
}

export interface WorkerHeartbeat {
    worker_id: string;
    version: string;
    sent_at: number;
    started_at: number | null;
    api_host: string | null;
    interval: number;
    clock: ClockSample | null;
    chrony: ChronyStatus;
    gps: GpsStatus;
    system: SystemInfo;
    runtime: WorkerRuntime;
}

export interface WorkerBoardEntry {
    worker_id: string;
    online: boolean;
    age: number;
    status: CheckStatus;
    checks: StatusCheck[];
    heartbeat: WorkerHeartbeat;
}

export interface DeviceBoardEntry {
    device_id: string;
    ip: string;
    hostname: string | null;
    in_session: boolean;
    online: boolean;
    reports_health: boolean;
    last_seen_age: number | null;
    rts_ids: string[];
    status: CheckStatus;
    checks: StatusCheck[];
    workers: WorkerBoardEntry[];
    clock: ClockSample | null;
    chrony: ChronyStatus | null;
    gps: GpsStatus | null;
    system: SystemInfo | null;
}

export interface InstrumentReport {
    ok: boolean;
    source: string;
    errors: string[];
    collected_at: number | null;
    received_at: number;
    instrument_name: string | null;
    serial_number: number | null;
    software_version: string | null;
    battery_capacity: number | null;
    power_source: string | null;
    internal_temperature: number | null;
    face: number | null;
    latency_mean: number | null;
    latency_max: number | null;
    latency_samples: number | null;
}

export interface TrackingQuality {
    samples: number;
    rate_hz: number | null;
    last_measurement_age: number | null;
    no_distance_ratio: number | null;
    error_ratio: number | null;
    timing_residual_std: number | null;
    timing_residual_max: number | null;
    clock_drift_ppm: number | null;
}

export interface RTSBoardEntry {
    rts_id: string;
    name: string;
    device_id: string;
    device_ip: string | null;
    port: string;
    baudrate: number;
    state: 'idle' | 'pending' | 'running';
    running_job: RTSJobResponse | null;
    pending_jobs: number;
    last_job: RTSJobResponse | null;
    instrument: InstrumentReport | null;
    tracking: TrackingQuality | null;
    status: CheckStatus;
    checks: StatusCheck[];
}

export interface ExternalSensorBoardEntry {
    id: string;
    name: string;
    ip: string;
    online: boolean;
    logging_active: boolean;
    last_seen_age: number | null;
    status: CheckStatus;
    checks: StatusCheck[];
}

export interface StatusBoardResponse {
    server_time: number;
    overall: CheckStatus;
    counts: Record<CheckStatus, number>;
    network_checks: StatusCheck[];
    devices: DeviceBoardEntry[];
    rts: RTSBoardEntry[];
    external_sensors: ExternalSensorBoardEntry[];
}
