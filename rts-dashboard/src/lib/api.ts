import type {
    Device,
    ExternalSensor,
    Job,
    JobPage,
    JobStatus,
    JobType,
    MeasurementSeries,
    RTS,
    RTSConfig,
    SensorRoles,
    SensorTrack,
    ServerInfo,
    Session,
    Health,
    InternalDelayEstimate,
    SynchronizerState,
    TrackingSettings,
} from './types';

const STORAGE_KEY = 'rts-api-url';
const DEFAULT_TIMEOUT = 15000;

export function apiBase(): string {
    try {
        return localStorage.getItem(STORAGE_KEY) || '/api';
    } catch {
        return '/api';
    }
}

export function setApiBase(url: string | null): void {
    try {
        if (url) localStorage.setItem(STORAGE_KEY, url.replace(/\/+$/, ''));
        else localStorage.removeItem(STORAGE_KEY);
    } catch {
        /* storage not available */
    }
}

export function eventsUrl(): string {
    const base = apiBase();
    if (/^https?:\/\//.test(base)) return base.replace(/^http/, 'ws') + '/events';
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${location.host}${base}/events`;
}

export class ApiError extends Error {
    constructor(
        public status: number,
        message: string,
    ) {
        super(message);
    }
}

async function request<T>(path: string, options: RequestInit & { timeout?: number } = {}): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), options.timeout ?? DEFAULT_TIMEOUT);
    const headers: Record<string, string> = { ...(options.headers as Record<string, string>) };
    if (options.body) headers['Content-Type'] = 'application/json';
    let response: Response;
    try {
        response = await fetch(`${apiBase()}${path}`, { ...options, headers, signal: controller.signal });
    } catch (e) {
        if ((e as Error).name === 'AbortError') throw new ApiError(0, 'The server did not answer in time');
        throw new ApiError(0, 'Server not reachable');
    } finally {
        clearTimeout(timer);
    }
    if (!response.ok) {
        let message = response.statusText;
        try {
            const body = await response.json();
            message = body.message || message;
        } catch {
            /* not JSON */
        }
        throw new ApiError(response.status, message);
    }
    if (response.status === 204) return undefined as T;
    return response.json();
}

const json = (method: string, body?: unknown): RequestInit => ({
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
});

function query(params: Record<string, string | number | boolean | null | undefined | string[]>): string {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
        if (value == null) continue;
        if (Array.isArray(value)) value.forEach((v) => search.append(key, v));
        else search.set(key, String(value));
    }
    const text = search.toString();
    return text ? `?${text}` : '';
}

export const api = {
    ping: () => request<void>('/ping', { timeout: 5000 }),
    info: () => request<ServerInfo>('/info'),

    sessions: () => request<Session[]>('/sessions'),
    session: (id: string) => request<Session>(`/sessions/${id}`),
    createSession: (name: string, notes = '') => request<Session>('/sessions', json('POST', { name, notes })),
    updateSession: (id: string, data: Partial<Pick<Session, 'name' | 'notes' | 'archived'>>) =>
        request<Session>(`/sessions/${id}`, json('PATCH', data)),
    deleteSession: (id: string) => request<void>(`/sessions/${id}`, { method: 'DELETE', timeout: 120000 }),

    devices: () => request<Device[]>('/devices'),
    updateDevice: (id: string, name: string | null) => request<Device>(`/devices/${id}`, json('PATCH', { name })),
    deleteDevice: (id: string) => request<void>(`/devices/${id}`, { method: 'DELETE' }),

    rtsList: (sessionId: string) => request<RTS[]>(`/rts${query({ session_id: sessionId })}`),
    createRts: (data: RTSConfig & { session_id: string; device_id: string | null; tracking?: TrackingSettings }) =>
        request<RTS>('/rts', json('POST', data)),
    updateRts: (id: string, data: Partial<RTSConfig> & { device_id?: string | null; tracking?: TrackingSettings }) =>
        request<RTS>(`/rts/${id}`, json('PATCH', data)),
    deleteRts: (id: string) => request<void>(`/rts/${id}`, { method: 'DELETE' }),

    jobs: (params: {
        session_id?: string;
        rts_id?: string;
        status?: JobStatus[];
        type?: JobType[];
        with_measurements?: boolean;
        before?: number | null;
        before_no?: number | null;
        limit?: number;
    }) =>
        request<JobPage>(
            `/jobs${query({
                session_id: params.session_id,
                rts_id: params.rts_id,
                status: params.status,
                type: params.type,
                with_measurements: params.with_measurements || undefined,
                before: params.before,
                before_no: params.before_no,
                limit: params.limit,
            })}`,
        ),
    job: (id: string) => request<Job>(`/jobs/${id}`),
    createJob: (rtsId: string, type: JobType, payload: Record<string, unknown> = {}) =>
        request<Job>('/jobs', json('POST', { rts_id: rtsId, type, payload })),
    stopJob: (id: string) => request<Job>(`/jobs/${id}/stop`, { method: 'POST' }),
    updateJob: (id: string, note: string) => request<Job>(`/jobs/${id}`, json('PATCH', { note })),
    deleteJob: (id: string) => request<void>(`/jobs/${id}`, { method: 'DELETE' }),
    measurements: (id: string, params: { from_seq?: number; to_seq?: number; max_points?: number } = {}) =>
        request<MeasurementSeries>(`/jobs/${id}/measurements${query(params)}`, { timeout: 60000 }),
    internalDelay: (id: string, apply = false) =>
        request<InternalDelayEstimate>(`/jobs/${id}/internal-delay${query({ apply: apply || undefined })}`, { method: 'POST', timeout: 120000 }),

    health: (sessionId: string) => request<Health>(`/health${query({ session_id: sessionId })}`),

    externalSensors: () => request<ExternalSensor[]>('/external-sensors'),
    sensorTracks: (seconds = 120) => request<SensorTrack[]>(`/external-sensors/live${query({ seconds })}`),
    updateExternalSensor: (id: string, data: { name?: string; logging_active?: boolean }) =>
        request<ExternalSensor>(`/external-sensors/${id}`, json('PATCH', data)),
    deleteExternalSensor: (id: string) => request<void>(`/external-sensors/${id}`, { method: 'DELETE', timeout: 120000 }),

    syncRoles: () => request<SensorRoles>('/synchronizer/roles'),
    setSyncRoles: (roles: SensorRoles) => request<SensorRoles>('/synchronizer/roles', json('PUT', roles)),
    syncState: () => request<SynchronizerState>('/synchronizer/state'),
    resetSync: () => request<void>('/synchronizer/reset', { method: 'POST' }),
};

// ── Downloads ───────────────────────────────────────────────────────────

interface AndroidBridge {
    saveFile?: (filename: string, content: string) => void;
    saveBase64?: (filename: string, base64: string, mimeType: string) => void;
}

function filenameFrom(response: Response, fallback: string): string {
    const disposition = response.headers.get('content-disposition') || '';
    const match = disposition.match(/filename="?([^";]+)"?/);
    return match ? match[1] : fallback;
}

/** Downloads a file from the API (works in browsers and in the Android app). */
export async function download(path: string, fallbackName: string): Promise<string> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 600000);
    let response: Response;
    try {
        response = await fetch(`${apiBase()}${path}`, { signal: controller.signal });
    } catch {
        throw new ApiError(0, 'Server not reachable');
    } finally {
        clearTimeout(timer);
    }
    if (!response.ok) {
        let message = response.statusText;
        try {
            message = (await response.json()).message || message;
        } catch {
            /* not JSON */
        }
        throw new ApiError(response.status, message);
    }
    const filename = filenameFrom(response, fallbackName);
    const blob = await response.blob();

    const android = (window as unknown as { RTSAndroid?: AndroidBridge }).RTSAndroid;
    if (android) {
        if (android.saveBase64) {
            const buffer = new Uint8Array(await blob.arrayBuffer());
            let binary = '';
            for (let i = 0; i < buffer.length; i += 0x8000) {
                binary += String.fromCharCode(...buffer.subarray(i, i + 0x8000));
            }
            android.saveBase64(filename, btoa(binary), blob.type || 'application/octet-stream');
            return filename;
        }
        if (android.saveFile && !filename.endsWith('.zip')) {
            android.saveFile(filename, await blob.text());
            return filename;
        }
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    return filename;
}
