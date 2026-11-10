<!--
    Measure: problems (only if any), one row per station with its main action, and one plot.
    Running jobs follow the event stream (gaps are filled from the server); idle stations show
    their most recent measurement.
-->
<script lang="ts">
    import { api } from '../api';
    import { clock } from '../clock.svelte';
    import PlotPanel, { type Trace } from '../components/PlotPanel.svelte';
    import Problems from '../components/Problems.svelte';
    import StationRow from '../components/StationRow.svelte';
    import Button from '../components/ui/Button.svelte';
    import Segmented from '../components/ui/Segmented.svelte';
    import { confirm } from '../confirm.svelte';
    import { rtsColor } from '../format';
    import { live, type Columns } from '../live.svelte';
    import { loadPref, savePref, thin, type Plotted } from '../plotdata';
    import { href } from '../router.svelte';
    import { store } from '../store.svelte';
    import { MEASURING_TYPES, TRACKING_TYPES } from '../types';

    type Window = 60 | 600 | 0;
    let windowSeconds = $state<Window>(loadPref('rts-window-v2', 60));
    $effect(() => savePref('rts-window-v2', windowSeconds));

    let rows = $derived(
        store.rts.map((rts, index) => {
            const running = store.runningJobOf(rts.id);
            const measuring = running && MEASURING_TYPES.includes(running.type) ? running : undefined;
            const job = measuring ?? store.lastMeasuringJob[rts.id];
            const isLive = !!measuring && TRACKING_TYPES.includes(measuring.type);
            return { rts, color: rtsColor(index), job, live: isLive, series: job ? live.get(job, isLive) : undefined };
        }),
    );
    let anyLive = $derived(rows.some((r) => r.live));
    let idle = $derived(rows.filter((r) => store.activeJobsOf(r.rts.id).length === 0));
    let measuring = $derived(rows.filter((r) => r.live));

    // Redraw at most 4× per second, not on every message
    let tick = $state(0);
    let lastVersions = '';
    $effect(() => {
        const timer = setInterval(() => {
            const versions = rows.map((r) => r.series?.version ?? 0).join(',');
            if (versions !== lastVersions || anyLive) {
                lastVersions = versions;
                tick++;
            }
        }, 250);
        return () => clearInterval(timer);
    });

    // "All": overview of the whole running job, refreshed every 20 s, plus the live tail
    let overviews = $state.raw<Record<string, Columns>>({});
    $effect(() => {
        if (windowSeconds !== 0) return;
        const jobs = rows.filter((r) => r.live && r.job).map((r) => r.job!);
        const refresh = () => {
            for (const job of jobs) {
                api.measurements(job.id, { max_points: 4000 })
                    .then((s) => (overviews = { ...overviews, [job.id]: s }))
                    .catch(() => {});
            }
        };
        refresh();
        const timer = setInterval(refresh, 20000);
        return () => clearInterval(timer);
    });

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

    function visible(r: (typeof rows)[number]): Plotted | null {
        const s = r.series;
        if (!s || s.cols.t.length === 0) return null;
        const n = s.cols.t.length;
        if (windowSeconds === 0) {
            const overview = r.live ? overviews[r.job!.id] : undefined;
            if (!overview || overview.seq.length === 0) return thin([{ cols: s.cols, from: 0, to: n }]);
            return thin([
                { cols: overview, from: 0, to: overview.seq.length },
                { cols: s.cols, from: firstSeqAfter(s.cols.seq, overview.seq[overview.seq.length - 1]), to: n },
            ]);
        }
        const end = r.live ? clock.server : s.lastT!;
        return thin([{ cols: s.cols, from: s.indexAt(end - windowSeconds - 1), to: n }]);
    }

    let traces = $derived.by<Trace[]>(() => {
        void tick;
        void overviews;
        void windowSeconds;
        return rows
            .filter((r) => !anyLive || r.live || windowSeconds === 0)
            .map((r) => ({
                label: r.rts.name,
                color: r.color,
                station: { x: r.rts.station_x, y: r.rts.station_y },
                live: r.live,
                data: visible(r),
            }));
    });

    async function startAll() {
        for (const r of idle) await store.startJob(r.rts.id, 'track_prism');
    }

    async function stopAll() {
        const ok = await confirm({
            title: `Stop all ${measuring.length} stations?`,
            message: 'The total stations stop measuring. Everything measured so far is kept.',
            confirm: 'Stop all',
            danger: true,
        });
        if (!ok) return;
        for (const r of measuring) {
            const job = store.runningJobOf(r.rts.id);
            if (job) await store.stopJob(job);
        }
    }
</script>

{#if store.rts.length === 0}
    <div class="mx-auto mt-12 max-w-md text-center">
        <p class="text-xl font-semibold">No total stations yet</p>
        <p class="mt-2 text-muted">Add the total stations of this session and their position first.</p>
        <Button variant="primary" class="mt-6" href={href(store.session?.id ?? null, 'setup')}>Go to setup</Button>
    </div>
{:else}
    <div class="space-y-6">
        <Problems />

        <section>
            <div class="mb-3 flex items-center gap-2">
                <h1 class="mr-auto text-xl font-semibold">Stations</h1>
                {#if measuring.length > 1}<Button variant="quiet" onclick={stopAll}>Stop all</Button>{/if}
                {#if idle.length > 1}<Button variant="quiet" onclick={startAll}>Start all</Button>{/if}
            </div>
            <ul class="card">
                {#each rows as r (r.rts.id)}
                    <StationRow rts={r.rts} color={r.color} lastJob={store.lastMeasuringJob[r.rts.id]} series={r.series} />
                {/each}
            </ul>
        </section>

        <PlotPanel {traces} version={tick} follow={anyLive && windowSeconds > 0 ? windowSeconds : 0}>
            {#snippet controls()}
                <h2 class="mr-auto text-lg font-semibold">{anyLive ? 'Live' : 'Last measurements'}</h2>
                <Segmented
                    label="Time span"
                    bind:value={windowSeconds}
                    options={[
                        { value: 60, label: '1 min' },
                        { value: 600, label: '10 min' },
                        { value: 0, label: 'All' },
                    ]}
                />
            {/snippet}
        </PlotPanel>
    </div>
{/if}
