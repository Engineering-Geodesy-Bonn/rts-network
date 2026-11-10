<!--
    Live view of the session: one card per RTS, the plan view and time series.
    Running jobs follow the event stream (gaps are filled from the server); idle RTS show
    their most recent measuring job, so past and current measurements are always visible.
-->
<script lang="ts">
    import { api } from '../api';
    import { clock } from '../clock.svelte';
    import PlanPlot, { type PlanTrack } from '../components/plots/PlanPlot.svelte';
    import TimePlot, { type TimeSeries } from '../components/plots/TimePlot.svelte';
    import RtsLiveCard from '../components/RtsLiveCard.svelte';
    import Button from '../components/ui/Button.svelte';
    import Icon from '../components/ui/Icon.svelte';
    import { confirm } from '../confirm.svelte';
    import { events } from '../events.svelte';
    import { rtsColor, units } from '../format';
    import { live, type Columns, type JobSeries } from '../live.svelte';
    import { href } from '../router.svelte';
    import { store } from '../store.svelte';
    import type { Job, RTS } from '../types';
    import { MEASURING_TYPES, TRACKING_TYPES } from '../types';

    type Window = 30 | 120 | 600 | 0; // seconds, 0 = whole job
    const WINDOWS: { value: Window; label: string }[] = [
        { value: 30, label: '30 s' },
        { value: 120, label: '2 min' },
        { value: 600, label: '10 min' },
        { value: 0, label: 'Whole job' },
    ];

    function loadPref<T>(key: string, fallback: T): T {
        try {
            const v = localStorage.getItem(key);
            return v === null ? fallback : (JSON.parse(v) as T);
        } catch {
            return fallback;
        }
    }
    function savePref(key: string, value: unknown) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch {
            /* ignore */
        }
    }

    let windowSeconds = $state<Window>(loadPref('rts-window', 120));
    let quantity = $state<'xyz' | 'polar'>(loadPref('rts-quantity', 'xyz'));
    $effect(() => savePref('rts-window', windowSeconds));
    $effect(() => savePref('rts-quantity', quantity));

    interface Display {
        rts: RTS;
        color: string;
        job: Job | undefined;
        running: boolean;
        series: JobSeries | undefined;
    }

    let displays = $derived<Display[]>(
        store.rts.map((rts, index) => {
            const runningJob = store.runningJobOf(rts.id);
            const runningMeasuring = runningJob && MEASURING_TYPES.includes(runningJob.type) ? runningJob : undefined;
            const job = runningMeasuring ?? store.lastMeasuringJob[rts.id];
            const isLive = !!runningMeasuring && TRACKING_TYPES.includes(runningMeasuring.type);
            return {
                rts,
                color: rtsColor(index),
                job,
                running: isLive,
                series: job ? live.get(job, isLive) : undefined,
            };
        }),
    );

    let anyRunning = $derived(displays.some((d) => d.running));

    // Redraw at a fixed rate (not on every message): at most 4 times per second, and only if
    // new data arrived or the time window moved.
    const MAX_PLOT_POINTS = 2000; // per station and plot: more than a plot has pixels
    let tick = $state(0);
    let lastVersions = '';
    $effect(() => {
        const timer = setInterval(() => {
            const versions = displays.map((d) => d.series?.version ?? 0).join(',');
            if (versions !== lastVersions || anyRunning) {
                lastVersions = versions;
                tick++;
            }
        }, 250);
        return () => clearInterval(timer);
    });
    // first data of a newly shown job: draw immediately
    let version = $derived(tick);

    // Whole-job overviews of running jobs (refreshed periodically, live points appended)
    let overviews = $state.raw<Record<string, Columns>>({});
    $effect(() => {
        if (windowSeconds !== 0) return;
        const running = displays.filter((d) => d.running && d.job);
        const refresh = () => {
            for (const d of running) {
                const job = d.job!;
                api.measurements(job.id, { max_points: 4000 })
                    .then((s) => (overviews = { ...overviews, [job.id]: s }))
                    .catch(() => {});
            }
        };
        refresh();
        const timer = setInterval(refresh, 20000);
        return () => clearInterval(timer);
    });

    type Plotted = { t: number[]; x: number[]; y: number[]; z: number[]; d: number[]; hz: number[]; v: number[] };
    const PLOT_KEYS = ['t', 'x', 'y', 'z', 'd', 'hz', 'v'] as const;

    /** Thins [from, to) of the columns to at most MAX_PLOT_POINTS (always keeping the last point). */
    function thin(sources: { cols: Columns; from: number; to: number }[]): Plotted {
        const total = sources.reduce((n, s) => n + Math.max(0, s.to - s.from), 0);
        const stride = Math.max(1, Math.ceil(total / MAX_PLOT_POINTS));
        const out: Plotted = { t: [], x: [], y: [], z: [], d: [], hz: [], v: [] };
        let k = 0;
        let last: { cols: Columns; i: number } | null = null;
        for (const { cols, from, to } of sources) {
            for (let i = from; i < to; i++, k++) {
                last = { cols, i };
                if (k % stride !== 0) continue;
                for (const key of PLOT_KEYS) out[key].push(cols[key][i] as number);
            }
        }
        if (last && (k - 1) % stride !== 0) {
            for (const key of PLOT_KEYS) out[key].push(last.cols[key][last.i] as number);
        }
        return out;
    }

    function firstSeqAfter(seq: number[], value: number): number {
        let lo = 0;
        let hi = seq.length;
        while (lo < hi) {
            const mid = (lo + hi) >> 1;
            if (seq[mid] <= value) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }

    /** The part of a job shown for the selected window. */
    function visible(d: Display): Plotted | null {
        const s = d.series;
        if (!s || s.cols.t.length === 0) return null;
        const n = s.cols.t.length;
        if (windowSeconds === 0) {
            const overview = d.running ? overviews[d.job!.id] : undefined;
            if (!overview || overview.seq.length === 0) return thin([{ cols: s.cols, from: 0, to: n }]);
            const lastSeq = overview.seq[overview.seq.length - 1];
            return thin([
                { cols: overview, from: 0, to: overview.seq.length },
                { cols: s.cols, from: firstSeqAfter(s.cols.seq, lastSeq), to: n },
            ]);
        }
        const end = d.running ? clock.server : s.lastT!;
        return thin([{ cols: s.cols, from: s.indexAt(end - windowSeconds - 1), to: n }]);
    }

    let data = $derived.by(() => {
        void tick;
        void overviews;
        void windowSeconds;
        return displays.map((d) => ({ d, cols: visible(d) }));
    });

    let tracks = $derived<PlanTrack[]>(
        data.map(({ d, cols }) => ({
            label: d.rts.name,
            color: d.color,
            x: cols?.x ?? [],
            y: cols?.y ?? [],
            station: { x: d.rts.station_x, y: d.rts.station_y },
            current: d.running,
            stale: !d.running,
        })),
    );

    // In follow mode only running jobs are in the time window; idle RTS appear when nothing runs
    let timeData = $derived(data.filter(({ d, cols }) => cols && (!anyRunning || d.running || windowSeconds === 0)));

    function series(pick: (c: Plotted) => number[], scale?: (v: number) => number): TimeSeries[] {
        return timeData.map(({ d, cols }) => ({
            label: d.rts.name,
            color: d.color,
            t: cols!.t,
            y: scale ? pick(cols!).map((v) => (v == null ? v : scale(v))) : pick(cols!),
        }));
    }

    let plots = $derived(
        quantity === 'xyz'
            ? [
                  { key: 'x', label: 'Easting (m)', series: series((c) => c.x) },
                  { key: 'y', label: 'Northing (m)', series: series((c) => c.y) },
                  { key: 'z', label: 'Height (m)', series: series((c) => c.z) },
              ]
            : [
                  { key: 'hz', label: 'Hz (gon)', series: series((c) => c.hz, units.radToGon) },
                  { key: 'v', label: 'V (gon)', series: series((c) => c.v, units.radToGon) },
                  { key: 'd', label: 'Distance (m)', series: series((c) => c.d) },
              ],
    );

    let follow = $derived(anyRunning && windowSeconds > 0 ? windowSeconds : 0);
    let idleCount = $derived(displays.filter((d) => !store.runningJobOf(d.rts.id) && store.activeJobsOf(d.rts.id).length === 0).length);
    let trackingCount = $derived(displays.filter((d) => d.running).length);

    async function startAll() {
        for (const d of displays) {
            if (store.activeJobsOf(d.rts.id).length === 0) await store.startJob(d.rts.id, 'track_prism');
        }
    }

    async function stopAll() {
        const ok = await confirm({
            title: 'Stop all tracking?',
            message: `${trackingCount} total station${trackingCount === 1 ? '' : 's'} stop measuring. All measurements recorded so far are kept.`,
            confirm: 'Stop all',
            danger: true,
        });
        if (!ok) return;
        for (const d of displays) {
            const job = store.runningJobOf(d.rts.id);
            if (job && TRACKING_TYPES.includes(job.type)) await store.stopJob(job);
        }
    }
</script>

{#if store.rts.length === 0}
    <div class="mx-auto mt-10 max-w-md rounded-2xl border border-dashed border-line p-10 text-center">
        <Icon name="crosshair" size={32} class="mx-auto text-muted" />
        <p class="mt-3 font-semibold">No total stations in this session</p>
        <p class="mt-1 text-sm text-muted">Add the total stations and their station setup first.</p>
        <Button variant="primary" class="mt-5" href={href(store.session?.id ?? null, 'stations')} icon="plus">Add total station</Button>
    </div>
{:else}
    <div class="mb-4 flex flex-wrap items-center gap-2">
        <h1 class="mr-auto text-xl font-bold">Measure</h1>
        {#if trackingCount > 0}
            <Button variant="danger" icon="stop" onclick={stopAll}>Stop all</Button>
        {/if}
        {#if idleCount > 0 && store.rts.length > 1}
            <Button variant="success" icon="play" onclick={startAll}>Start all ({idleCount})</Button>
        {/if}
    </div>

    <section class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {#each displays as d (d.rts.id)}
            <RtsLiveCard rts={d.rts} color={d.color} job={d.job} series={d.series} board={store.board?.rts.find((r) => r.rts_id === d.rts.id)} />
        {/each}
    </section>

    <div class="mt-4 flex flex-wrap items-center gap-2">
        <div class="inline-flex rounded-lg border border-line bg-surface p-0.5" role="group" aria-label="Time window">
            {#each WINDOWS as w (w.value)}
                <button
                    class="rounded-md px-3 py-1.5 text-sm font-medium {windowSeconds === w.value ? 'bg-accent text-accent-fg' : 'text-muted hover:text-fg'}"
                    onclick={() => (windowSeconds = w.value)}>{w.label}</button
                >
            {/each}
        </div>
        <div class="inline-flex rounded-lg border border-line bg-surface p-0.5" role="group" aria-label="Quantity">
            <button class="rounded-md px-3 py-1.5 text-sm font-medium {quantity === 'xyz' ? 'bg-accent text-accent-fg' : 'text-muted hover:text-fg'}" onclick={() => (quantity = 'xyz')}>E / N / H</button>
            <button class="rounded-md px-3 py-1.5 text-sm font-medium {quantity === 'polar' ? 'bg-accent text-accent-fg' : 'text-muted hover:text-fg'}" onclick={() => (quantity = 'polar')}>Hz / V / D</button>
        </div>
        <span class="ml-auto text-xs text-muted">
            {#if events.state !== 'open'}
                <span class="font-semibold text-fail">Not receiving live data</span>
            {:else if anyRunning}
                Live · updates 5× per second
            {:else}
                Showing the most recent measurements of each station
            {/if}
        </span>
    </div>

    <section class="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] [&>*]:min-w-0">
        <div class="rounded-xl border border-line bg-surface p-3 shadow-sm">
            <h2 class="mb-2 text-sm font-semibold text-muted">Plan view</h2>
            <PlanPlot {tracks} {version} height={420} />
        </div>
        <div class="space-y-3">
            {#each plots as p (p.key + quantity)}
                <div class="rounded-xl border border-line bg-surface p-3 shadow-sm">
                    <TimePlot series={p.series} {version} yLabel={p.label} height={150} {follow} now={() => clock.server} />
                </div>
            {/each}
        </div>
    </section>
{/if}
