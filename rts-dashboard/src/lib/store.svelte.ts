/** State of the open session, kept in sync by the event stream. */
import { api } from './api';
import { events } from './events.svelte';
import { live } from './live.svelte';
import { toast } from './toast.svelte';
import type { Device, Job, RTS, Session, StatusBoard } from './types';
import { ACTIVE_STATUSES, MEASURING_TYPES } from './types';

class AppStore {
    session = $state<Session | null>(null);
    sessionError = $state('');
    rts = $state<RTS[]>([]);
    devices = $state<Device[]>([]);
    /** Active (pending/running/lost) jobs of the session by id */
    activeJobs = $state<Record<string, Job>>({});
    /** Most recent job with measurements per RTS (shown when the RTS is idle) */
    lastMeasuringJob = $state<Record<string, Job>>({});
    board = $state<StatusBoard | null>(null);
    boardReceivedAt = $state(0);
    /** Incremented on every job event, for lists that show jobs */
    jobsVersion = $state(0);
    lastJobEvent = $state<Job | null>(null);
    loading = $state(false);

    constructor() {
        events.on((event) => {
            switch (event.type) {
                case 'status':
                    if (event.board.session_id === this.session?.id) {
                        this.board = event.board;
                        this.boardReceivedAt = Date.now();
                    }
                    break;
                case 'job':
                    this.onJob(event.job);
                    break;
                case 'job_deleted':
                    delete this.activeJobs[event.job_id];
                    live.forget(event.job_id);
                    this.jobsVersion++;
                    break;
                case 'changed':
                    void this.onChanged(event.entity, event.session_id);
                    break;
            }
        });
        events.onOpen((reconnect) => {
            if (reconnect && this.session) void this.refresh();
        });
    }

    rtsById(id: string | null | undefined): RTS | undefined {
        return this.rts.find((r) => r.id === id);
    }

    rtsIndex(id: string | null | undefined): number {
        return this.rts.findIndex((r) => r.id === id);
    }

    deviceLabel(id: string | null | undefined): string {
        const device = this.devices.find((d) => d.id === id);
        if (!device) return 'No device';
        return device.name || device.hostname || device.ip;
    }

    activeJobsOf(rtsId: string): Job[] {
        return Object.values(this.activeJobs)
            .filter((j) => j.rts_id === rtsId)
            .sort((a, b) => a.created_at - b.created_at);
    }

    runningJobOf(rtsId: string): Job | undefined {
        return this.activeJobsOf(rtsId).find((j) => j.status === 'running' || j.status === 'lost');
    }

    private onJob(job: Job): void {
        const inSession = this.rts.some((r) => r.id === job.rts_id);
        if (!inSession) return;
        if (ACTIVE_STATUSES.includes(job.status)) {
            this.activeJobs[job.id] = job;
            if (job.status === 'running' && MEASURING_TYPES.includes(job.type)) live.watch(job);
        } else {
            delete this.activeJobs[job.id];
            if (job.status === 'failed' && job.error) {
                toast.error(`${this.rtsById(job.rts_id)?.name ?? 'RTS'}: ${job.error}`);
            }
        }
        if (MEASURING_TYPES.includes(job.type) && job.status !== 'pending' && job.status !== 'cancelled') {
            this.lastMeasuringJob[job.rts_id] = job;
        }
        this.lastJobEvent = job;
        this.jobsVersion++;
    }

    private async onChanged(entity: string, sessionId: string | null): Promise<void> {
        if (!this.session) return;
        try {
            if (entity === 'rts' || entity === 'session') {
                if (entity === 'session' && sessionId === null) {
                    const session = await api.session(this.session.id).catch(() => null);
                    if (session) this.session = session;
                }
                this.rts = await api.rtsList(this.session.id);
            } else if (entity === 'device') {
                this.devices = await api.devices();
            }
        } catch {
            /* refreshed on the next event or reconnect */
        }
    }

    async open(sessionId: string): Promise<void> {
        if (this.session?.id === sessionId) return;
        this.session = null;
        this.board = null;
        this.rts = [];
        this.activeJobs = {};
        this.lastMeasuringJob = {};
        this.sessionError = '';
        events.subscribe(sessionId);
        await this.refresh(sessionId);
    }

    close(): void {
        this.session = null;
        this.board = null;
        events.subscribe(null);
    }

    /** Loads everything of the session (on open and after a reconnect). */
    async refresh(sessionId = this.session?.id): Promise<void> {
        if (!sessionId) return;
        this.loading = true;
        try {
            const [session, rts, devices, active] = await Promise.all([
                api.session(sessionId),
                api.rtsList(sessionId),
                api.devices(),
                api.jobs({ session_id: sessionId, status: ACTIVE_STATUSES, limit: 200 }),
            ]);
            this.session = session;
            this.rts = rts;
            this.devices = devices;
            this.activeJobs = Object.fromEntries(active.items.map((j) => [j.id, j]));
            const last: Record<string, Job> = {};
            await Promise.all(
                rts.map(async (r) => {
                    const page = await api.jobs({ rts_id: r.id, type: MEASURING_TYPES, with_measurements: true, limit: 1 });
                    const running = active.items.find((j) => j.rts_id === r.id && j.status !== 'pending' && MEASURING_TYPES.includes(j.type));
                    const job = running ?? page.items[0];
                    if (job) last[r.id] = job;
                }),
            );
            this.lastMeasuringJob = last;
            this.sessionError = '';
            api.status(sessionId)
                .then((board) => {
                    if (this.session?.id === sessionId) {
                        this.board = board;
                        this.boardReceivedAt = Date.now();
                    }
                })
                .catch(() => {});
        } catch (e) {
            this.sessionError = (e as Error).message;
        } finally {
            this.loading = false;
        }
    }

    /** Runs a job action with error reporting. */
    async startJob(rtsId: string, type: Job['type']): Promise<Job | null> {
        try {
            const job = await api.createJob(rtsId, type);
            this.onJob(job);
            return job;
        } catch (e) {
            toast.error((e as Error).message);
            return null;
        }
    }

    async stopJob(job: Job): Promise<void> {
        try {
            this.onJob(await api.stopJob(job.id));
        } catch (e) {
            toast.error((e as Error).message);
        }
    }
}

export const store = new AppStore();
