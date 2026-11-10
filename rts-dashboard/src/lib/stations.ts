/** The stations of the open session with the job shown for each (running or last measured). */
import { rtsColor } from './format';
import { live, type JobSeries } from './live.svelte';
import { store } from './store.svelte';
import type { Job, RTS } from './types';
import { MEASURING_TYPES, TRACKING_TYPES } from './types';

export interface StationRow {
    rts: RTS;
    color: string;
    /** Running measuring job, otherwise the last job with measurements */
    job: Job | undefined;
    /** The job is tracking right now (data arrives over the event stream) */
    live: boolean;
    series: JobSeries | undefined;
}

export function stationRows(): StationRow[] {
    return store.rts.map((rts, index) => {
        const running = store.runningJobOf(rts.id);
        const measuring = running && MEASURING_TYPES.includes(running.type) ? running : undefined;
        const job = measuring ?? store.lastMeasuringJob[rts.id];
        const isLive = !!measuring && TRACKING_TYPES.includes(measuring.type);
        return { rts, color: rtsColor(index), job, live: isLive, series: job ? live.get(job, isLive) : undefined };
    });
}

/** A counter that increases at most `hz` times per second while data changes (redraw trigger). */
export function redrawTicker(rows: () => StationRow[], onTick: () => void, hz = 4): () => void {
    let last = '';
    const timer = setInterval(() => {
        const current = rows();
        const versions = current.map((r) => r.series?.version ?? 0).join(',');
        if (versions !== last || current.some((r) => r.live)) {
            last = versions;
            onTick();
        }
    }, 1000 / hz);
    return () => clearInterval(timer);
}
