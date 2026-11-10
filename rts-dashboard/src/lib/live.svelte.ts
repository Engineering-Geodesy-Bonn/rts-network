/**
 * Measurements of the jobs shown in the dashboard.
 *
 * A JobSeries holds the measurements of one job in seq order. Running jobs receive new
 * points over the event stream; gaps (missed messages, reconnects, phone asleep) are detected
 * from the sequence numbers and filled from the API, so the view always converges to what is
 * stored on the server. Finished jobs are loaded once (thinned out for long jobs).
 */
import { api } from './api';
import { events } from './events.svelte';
import type { Job, LiveMessage, MeasurementSeries } from './types';

const LIVE_CAPACITY = 25 * 60 * 20; // 20 min at 25 Hz in memory per running job
const OVERVIEW_POINTS = 6000; // points of a whole-job overview
const MAX_SERIES = 16;

export interface Columns {
    seq: number[];
    t: number[];
    x: number[];
    y: number[];
    z: number[];
    d: number[];
    hz: number[];
    v: number[];
    ok: boolean[];
}

function emptyColumns(): Columns {
    return { seq: [], t: [], x: [], y: [], z: [], d: [], hz: [], v: [], ok: [] };
}

const KEYS: (keyof Columns)[] = ['seq', 't', 'x', 'y', 'z', 'd', 'hz', 'v', 'ok'];

function fromSeries(s: MeasurementSeries | LiveMessage): Columns {
    return { seq: s.seq, t: s.t, x: s.x, y: s.y, z: s.z, d: s.d, hz: s.hz, v: s.v, ok: s.ok };
}

/** Merges b into a (both sorted by seq), without duplicates. */
function merge(a: Columns, b: Columns): Columns {
    if (b.seq.length === 0) return a;
    if (a.seq.length === 0) return b;
    const out = emptyColumns();
    let i = 0;
    let j = 0;
    const push = (src: Columns, k: number) => {
        for (const key of KEYS) (out[key] as unknown[]).push(src[key][k]);
    };
    while (i < a.seq.length || j < b.seq.length) {
        if (j >= b.seq.length || (i < a.seq.length && a.seq[i] < b.seq[j])) push(a, i++);
        else if (i >= a.seq.length || b.seq[j] < a.seq[i]) push(b, j++);
        else {
            push(b, j++);
            i++;
        }
    }
    return out;
}

export class JobSeries {
    jobId: string;
    rtsId: string;
    /** Number of measurements stored on the server (from the last message or load) */
    total = $state(0);
    /** Incremented on every change: plots redraw when it changes */
    version = $state(0);
    loading = $state(false);
    error = $state('');
    /** 1 if every measurement is loaded, n if only every n-th (overview of a long job) */
    stride = $state(1);
    live: boolean;
    cols: Columns = emptyColumns();
    lastUsed = Date.now();
    private filling = false;
    private pendingGap: [number, number | undefined] | null = null;

    constructor(job: Job, live: boolean) {
        this.jobId = job.id;
        this.rtsId = job.rts_id;
        this.total = job.count;
        this.live = live;
    }

    get lastSeq(): number {
        return this.cols.seq.length ? this.cols.seq[this.cols.seq.length - 1] : -1;
    }

    get lastT(): number | null {
        return this.cols.t.length ? this.cols.t[this.cols.t.length - 1] : null;
    }

    private bump(): void {
        this.version++;
    }

    private trim(): void {
        if (!this.live) return;
        const excess = this.cols.seq.length - LIVE_CAPACITY;
        if (excess > 1000) {
            for (const key of KEYS) this.cols[key].splice(0, excess);
        }
    }

    /** Loads the latest measurements (running job) or an overview of the whole job. */
    async load(): Promise<void> {
        await Promise.resolve(); // may be triggered while a component derives its state
        this.loading = true;
        this.error = '';
        try {
            if (this.live) {
                const from = Math.max(0, this.total - LIVE_CAPACITY);
                const data = await api.measurements(this.jobId, { from_seq: from, max_points: LIVE_CAPACITY });
                this.cols = merge(fromSeries(data), this.cols);
                this.total = Math.max(this.total, data.total + from);
                this.stride = 1;
            } else {
                const data = await api.measurements(this.jobId, { max_points: OVERVIEW_POINTS });
                this.cols = fromSeries(data);
                this.total = data.total;
                this.stride = data.stride;
            }
            this.trim();
            this.bump();
        } catch (e) {
            this.error = (e as Error).message;
        } finally {
            this.loading = false;
        }
    }

    /** New points from the event stream. */
    add(message: LiveMessage): void {
        this.lastUsed = Date.now();
        this.total = Math.max(this.total, message.count);
        if (message.seq.length === 0) return;
        const first = message.seq[0];
        if (this.cols.seq.length && first > this.lastSeq + 1) {
            this.fill(this.lastSeq + 1, first - 1);
        }
        if (this.cols.seq.length === 0 || first > this.lastSeq) {
            for (const key of KEYS) (this.cols[key] as unknown[]).push(...(message[key] as unknown[]));
        } else {
            this.cols = merge(this.cols, fromSeries(message));
        }
        this.trim();
        this.bump();
    }

    /** Fetches missing measurements from the server (after a gap or a reconnect). */
    async fill(from: number, to?: number): Promise<void> {
        if (this.filling) {
            this.pendingGap = [Math.min(from, this.pendingGap?.[0] ?? from), to === undefined || this.pendingGap?.[1] === undefined ? undefined : Math.max(to, this.pendingGap[1])];
            return;
        }
        this.filling = true;
        try {
            const data = await api.measurements(this.jobId, { from_seq: from, to_seq: to, max_points: LIVE_CAPACITY });
            this.cols = merge(this.cols, fromSeries(data));
            this.trim();
            this.bump();
        } catch {
            // retried on the next gap or reconnect
        } finally {
            this.filling = false;
            const next = this.pendingGap;
            this.pendingGap = null;
            if (next) void this.fill(next[0], next[1]);
        }
    }

    /** Index of the first point with t >= t0 */
    indexAt(t0: number): number {
        const t = this.cols.t;
        let lo = 0;
        let hi = t.length;
        while (lo < hi) {
            const mid = (lo + hi) >> 1;
            if (t[mid] < t0) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }
}

class LiveData {
    series = new Map<string, JobSeries>();

    constructor() {
        events.on((event) => {
            if (event.type === 'live') {
                const series = this.series.get(event.job_id);
                if (series) series.add(event);
            }
        });
        events.onOpen((reconnect) => {
            if (!reconnect) return;
            for (const series of this.series.values()) {
                if (series.live) void series.fill(series.lastSeq + 1);
            }
        });
    }

    /** Series of a job; running jobs follow the event stream. */
    get(job: Job, live: boolean): JobSeries {
        let series = this.series.get(job.id);
        if (series && series.live !== live) {
            // job ended: switch to the overview of the whole job
            series.live = live;
            if (!live) void series.load();
        }
        if (!series) {
            series = new JobSeries(job, live);
            this.series.set(job.id, series);
            void series.load();
            this.evict();
        }
        series.lastUsed = Date.now();
        return series;
    }

    /** Registers a job that is starting, so that no point of its event stream is missed. */
    watch(job: Job): void {
        if (!this.series.has(job.id)) {
            const series = new JobSeries(job, true);
            this.series.set(job.id, series);
            void series.load();
            this.evict();
        }
    }

    forget(jobId: string): void {
        this.series.delete(jobId);
    }

    private evict(): void {
        if (this.series.size <= MAX_SERIES) return;
        const candidates = [...this.series.values()].filter((s) => !s.live).sort((a, b) => a.lastUsed - b.lastUsed);
        while (this.series.size > MAX_SERIES && candidates.length) {
            this.series.delete(candidates.shift()!.jobId);
        }
    }
}

export const live = new LiveData();
