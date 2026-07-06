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
    | 'add_static_measurement';

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
