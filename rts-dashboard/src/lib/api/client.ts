import type {
    SessionResponse,
    CreateSessionRequest,
    RTSResponse,
    CreateRTSRequest,
    UpdateRTSRequest,
    TrackingSettingsResponse,
    UpdateTrackingSettingsRequest,
    MeasurementResponse,
    RTSJobResponse,
    CreateRTSJobRequest,
    RTSJobStatus,
    DeviceResponse,
    RTSStatusResponse,
    ExternalSensorResponse,
    SensorRolesResponse,
    SynchronizerStateResponse,
} from './types';

function getBaseUrl(): string {
    return localStorage.getItem('rts-api-url') || '/api';
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
    const url = `${getBaseUrl()}${path}`;
    const headers: Record<string, string> = { ...options?.headers as Record<string, string> };
    if (options?.body) {
        headers['Content-Type'] = 'application/json';
    }
    const res = await fetch(url, {
        ...options,
        headers,
    });
    if (!res.ok) {
        const body = await res.text().catch(() => '');
        throw new Error(`API ${res.status}: ${body || res.statusText}`);
    }
    if (res.status === 204) return undefined as T;
    return res.json();
}

// ── Health ──────────────────────────────────────────────────
export async function ping(): Promise<void> {
    await request<void>('/ping');
}

// ── Sessions ────────────────────────────────────────────────
export async function getSessions(): Promise<SessionResponse[]> {
    return request<SessionResponse[]>('/session');
}

export async function getSession(id: number): Promise<SessionResponse> {
    return request<SessionResponse>(`/session/${id}`);
}

export async function createSession(data: CreateSessionRequest): Promise<SessionResponse> {
    return request<SessionResponse>('/session', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function deleteSession(id: number): Promise<void> {
    await request<void>(`/session/${id}`, { method: 'DELETE' });
}

// ── RTS ─────────────────────────────────────────────────────
export async function getAllRts(sessionId: number): Promise<RTSResponse[]> {
    return request<RTSResponse[]>(`/rts?session_id=${sessionId}`);
}

export async function getRts(id: number): Promise<RTSResponse> {
    return request<RTSResponse>(`/rts/${id}`);
}

export async function createRts(data: CreateRTSRequest): Promise<RTSResponse> {
    return request<RTSResponse>('/rts/', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function updateRts(id: number, data: UpdateRTSRequest): Promise<RTSResponse> {
    return request<RTSResponse>(`/rts/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    });
}

export async function deleteRts(id: number): Promise<void> {
    await request<void>(`/rts/${id}`, { method: 'DELETE' });
}

export async function getRtsStatus(rtsId: number): Promise<RTSStatusResponse> {
    return request<RTSStatusResponse>(`/rts/${rtsId}/status`);
}

// ── Tracking Settings ───────────────────────────────────────
export async function getTrackingSettings(rtsId: number): Promise<TrackingSettingsResponse> {
    return request<TrackingSettingsResponse>(`/rts/${rtsId}/tracking_settings`);
}

export async function updateTrackingSettings(
    rtsId: number,
    data: UpdateTrackingSettingsRequest,
): Promise<UpdateTrackingSettingsRequest> {
    return request<UpdateTrackingSettingsRequest>(`/rts/${rtsId}/tracking_settings`, {
        method: 'PUT',
        body: JSON.stringify(data),
    });
}

// ── Measurements ────────────────────────────────────────────
export async function getLatestMeasurements(): Promise<MeasurementResponse[]> {
    return request<MeasurementResponse[]>('/measurements/latest');
}

export async function getRawMeasurements(jobId: number): Promise<MeasurementResponse[]> {
    return request<MeasurementResponse[]>(`/measurements/raw?job_id=${jobId}`);
}

export async function getCorrectedMeasurements(jobId: number): Promise<MeasurementResponse[]> {
    return request<MeasurementResponse[]>(`/measurements/corrected?job_id=${jobId}`);
}

export async function performStaticMeasurement(rtsId: number): Promise<MeasurementResponse> {
    return request<MeasurementResponse>('/measurements/static', {
        method: 'POST',
        body: JSON.stringify({ rts_id: rtsId }),
    });
}

// ── Measurement Downloads (CSV) ─────────────────────────────
async function downloadFile(path: string, fallbackName: string): Promise<void> {
    const url = `${getBaseUrl()}${path}`;
    const res = await fetch(url);
    if (!res.ok) {
        const body = await res.text().catch(() => '');
        throw new Error(`API ${res.status}: ${body || res.statusText}`);
    }
    const disposition = res.headers.get('content-disposition') || '';
    const match = disposition.match(/filename=(.+)/);
    const filename = match ? match[1].replace(/"/g, '') : fallbackName;
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
}

export async function downloadTrajectory(jobId: number): Promise<void> {
    await downloadFile(`/measurements/trajectory/${jobId}`, `trajectory_${jobId}.csv`);
}

export async function downloadRawMeasurements(jobId: number): Promise<void> {
    await downloadFile(`/measurements/download/${jobId}`, `raw_${jobId}.csv`);
}

// ── Session Export (download all jobs' data as zip/csv) ─────
export async function exportSession(sessionId: number): Promise<void> {
    // Get session's RTS, then all jobs, then filter to jobs belonging to session RTS
    const sessionRts = await getAllRts(sessionId);
    const rtsIds = new Set(sessionRts.map(r => r.id));
    const jobs = await getAllJobs();
    const downloadableTypes = new Set(['track_prism', 'dummy_tracking', 'static_measurement']);
    const downloadableJobs = jobs.filter(j =>
        rtsIds.has(j.rts_id!) && downloadableTypes.has(j.job_type) && (j.num_measurements ?? 0) > 0
    );

    for (const job of downloadableJobs) {
        await downloadRawMeasurements(job.job_id);
        if (job.job_type === 'track_prism' || job.job_type === 'dummy_tracking' || job.job_type === 'static_measurement') {
            await downloadTrajectory(job.job_id);
        }
    }
}

// ── Jobs ────────────────────────────────────────────────────
export async function getAllJobs(): Promise<RTSJobResponse[]> {
    return request<RTSJobResponse[]>('/jobs');
}

export async function getJob(id: number): Promise<RTSJobResponse> {
    return request<RTSJobResponse>(`/jobs/${id}`);
}

export async function createJob(data: CreateRTSJobRequest): Promise<RTSJobResponse> {
    return request<RTSJobResponse>('/jobs', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function deleteJob(id: number): Promise<void> {
    await request<void>(`/jobs/${id}`, { method: 'DELETE' });
}

export async function updateJobStatus(id: number, status: RTSJobStatus): Promise<RTSJobResponse> {
    return request<RTSJobResponse>(`/jobs/${id}?job_status=${status}`, { method: 'PUT' });
}

export async function getRunningJobs(): Promise<RTSJobResponse[]> {
    return request<RTSJobResponse[]>('/jobs/status/running');
}

// ── Devices ─────────────────────────────────────────────────
export async function getDevices(): Promise<DeviceResponse[]> {
    return request<DeviceResponse[]>('/devices');
}

export async function getDevice(id: number): Promise<DeviceResponse> {
    return request<DeviceResponse>(`/devices/${id}`);
}

export async function registerDevice(): Promise<DeviceResponse> {
    return request<DeviceResponse>('/devices/register', { method: 'POST' });
}

// ── External Sensors ───────────────────────────────────────
export async function getExternalSensors(): Promise<ExternalSensorResponse[]> {
    return request<ExternalSensorResponse[]>('/external_sensors');
}

export async function updateExternalSensor(
    id: number,
    name: string,
): Promise<ExternalSensorResponse> {
    return request<ExternalSensorResponse>(
        `/external_sensors/${id}?name=${encodeURIComponent(name)}`,
        { method: 'PUT' },
    );
}

export async function deleteExternalSensor(id: number): Promise<void> {
    await request<void>(`/external_sensors/${id}`, { method: 'DELETE' });
}

// ── Synchronizer ───────────────────────────────────────────
export async function getSensorRoles(): Promise<SensorRolesResponse> {
    return request<SensorRolesResponse>('/synchronizer/roles');
}

export async function setSensorRoles(
    primarySensorId: string | null,
    secondarySensorId: string | null,
): Promise<void> {
    const params = new URLSearchParams();
    if (primarySensorId != null) params.set('primary_sensor_id', primarySensorId);
    if (secondarySensorId != null) params.set('secondary_sensor_id', secondarySensorId);
    const qs = params.toString();
    await request<void>(`/synchronizer/roles${qs ? '?' + qs : ''}`, { method: 'PUT' });
}

export async function getSynchronizerState(): Promise<SynchronizerStateResponse> {
    return request<SynchronizerStateResponse>('/synchronizer/state');
}

export async function resetSynchronizer(): Promise<void> {
    await request<void>('/synchronizer/reset', { method: 'PATCH' });
}
