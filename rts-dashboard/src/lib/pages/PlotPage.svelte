<!--
    Plot: map and time plots.
    Stations: the selected stations, running jobs live, idle stations with their last measurement.
    Jobs: any measurements of the session overlaid, on clock time or aligned at their start.
    The selected jobs are part of the address (#/s/<session>/plot/<job>,<job>), so a view can be bookmarked.
-->
<script lang="ts">
    import { api } from '../api';
    import { clock } from '../clock.svelte';
    import JobPicker from '../components/JobPicker.svelte';
    import PlotPanel, { type Trace } from '../components/PlotPanel.svelte';
    import Button from '../components/ui/Button.svelte';
    import Icon from '../components/ui/Icon.svelte';
    import Segmented from '../components/ui/Segmented.svelte';
    import { fmtDateTime, fmtShortDuration, rtsColor } from '../format';
    import { live } from '../live.svelte';
    import { loadPref, savePref, thin, type Plotted } from '../plotdata';
    import { href, navigate, router } from '../router.svelte';
    import { redrawTicker, stationRows, type StationRow } from '../stations';
    import { store } from '../store.svelte';
    import { toast } from '../toast.svelte';
    import type { Job } from '../types';
    import { ACTIVE_STATUSES, TRACKING_TYPES } from '../types';

    const MAX_JOBS = 12;

    type Window = 60 | 600 | 3600 | 0;
    let windowSeconds = $state<Window>(loadPref('rts-window-v2', 60));
    let mode = $state<'position' | 'polar'>(loadPref('rts-mode', 'position'));
    let hidden = $state<string[]>(loadPref('rts-hidden-stations', []));
    let relative = $state<boolean>(loadPref('rts-plot-relative', false));
    $effect(() => savePref('rts-window-v2', windowSeconds));
    $effect(() => savePref('rts-mode', mode));
    $effect(() => savePref('rts-hidden-stations', hidden));
    $effect(() => savePref('rts-plot-relative', relative));

    // ── source: stations or chosen jobs ────────────────────────────────
    let selection = $derived((router.route.id ?? '').split(',').filter(Boolean));
    let preferJobs = $state<boolean>(loadPref('rts-plot-jobs-mode', false));
    let source = $derived<'stations' | 'jobs'>(selection.length || preferJobs ? 'jobs' : 'stations');
    let pickerOpen = $state(false);
    const savedKey = () => `rts-plot-jobs-${store.session?.id}`;

    function select(ids: string[]) {
        savePref(savedKey(), ids);
        navigate(href(store.session!.id, 'plot', ids.length ? ids.join(',') : null));
    }

    function setSource(value: 'stations' | 'jobs') {
        preferJobs = value === 'jobs';
        savePref('rts-plot-jobs-mode', preferJobs);
        if (value === 'stations') navigate(href(store.session!.id, 'plot'));
        else {
            const saved = loadPref<string[]>(savedKey(), []);
            if (saved.length) select(saved);
            else pickerOpen = true;
        }
    }

    // Coming back to the tab (address without jobs) restores the last chosen jobs
    $effect(() => {
        if (preferJobs && selection.length === 0 && store.session) {
            const saved = loadPref<string[]>(savedKey(), []);
            if (saved.length) select(saved);
        }
    });

    // ── stations ───────────────────────────────────────────────────────
    let rows = $derived(stationRows());
    let shown = $derived(rows.filter((r) => !hidden.includes(r.rts.id)));
    let anyLive = $derived(shown.some((r) => r.live));

    let tick = $state(0);
    $effect(() => (source === 'stations' ? redrawTicker(() => shown, () => tick++) : undefined));

    function toggle(id: string) {
        hidden = hidden.includes(id) ? hidden.filter((h) => h !== id) : [...hidden, id];
    }

    function visible(r: StationRow): Plotted | null {
        const s = r.series;
        if (!s || s.cols.t.length === 0) return null;
        return thin(s.window(windowSeconds, r.live ? clock.server : s.lastT!));
    }

    // While something is live, the time window follows "now": idle stations only appear with "Whole job"
    let stationTraces = $derived.by<Trace[]>(() => {
        void tick;
        void windowSeconds;
        return shown
            .filter((r) => !anyLive || r.live || windowSeconds === 0)
            .map((r) => ({ label: r.rts.name, color: r.color, station: { x: r.rts.station_x, y: r.rts.station_y }, live: r.live, data: visible(r) }));
    });

    function status(r: StationRow): string {
        if (r.live) return 'live';
        if (!r.job) return 'no data';
        return 'last measurement';
    }

    // ── jobs ───────────────────────────────────────────────────────────
    let jobs = $state<Record<string, Job>>({});
    let missing = $state<string[]>([]);

    $effect(() => {
        const wanted = selection.filter((id) => !jobs[id] && !missing.includes(id));
        for (const id of wanted) {
            api.job(id)
                .then((job) => (jobs[id] = job))
                .catch(() => {
                    missing = [...missing, id];
                    toast.error('A selected measurement no longer exists');
                });
        }
    });
    $effect(() => {
        const event = store.lastJobEvent;
        if (event && jobs[event.id]) jobs[event.id] = event;
    });

    interface Picked {
        job: Job;
        color: string;
        isLive: boolean;
    }
    let picked = $derived<Picked[]>(
        selection
            .map((id) => jobs[id])
            .filter((job): job is Job => !!job)
            .map((job, i) => ({ job, color: rtsColor(i), isLive: ACTIVE_STATUSES.includes(job.status) && TRACKING_TYPES.includes(job.type) })),
    );
    let series = $derived(source === 'jobs' ? picked.map((p) => ({ ...p, series: live.get(p.job, p.isLive) })) : []);

    let jobTick = $state(0);
    $effect(() => {
        if (source !== 'jobs') return;
        let last = '';
        const timer = setInterval(() => {
            const versions = series.map((s) => s.series.version).join(',');
            if (versions !== last) {
                last = versions;
                jobTick++;
            }
        }, 250);
        return () => clearInterval(timer);
    });

    function jobLabel(job: Job): string {
        return `${store.rtsById(job.rts_id)?.name ?? 'Removed station'} · ${fmtDateTime(job.first_t ?? job.created_at)}`;
    }

    let jobTraces = $derived.by<Trace[]>(() => {
        void jobTick;
        const drawn = new Set<string>(); // each station once on the map
        return series.map(({ job, color, isLive, series: s }) => {
            const rts = store.rtsById(job.rts_id);
            let data: Plotted | null = s.cols.t.length ? thin(s.whole(), 3000) : null;
            if (data && relative) {
                const t0 = job.first_t ?? data.t[0];
                data = { ...data, t: data.t.map((t) => t - t0) };
            }
            const first = rts && !drawn.has(rts.id);
            if (rts) drawn.add(rts.id);
            return {
                label: jobLabel(job),
                color,
                station: rts && first ? { x: rts.station_x, y: rts.station_y } : null,
                stationLabel: rts?.name,
                live: isLive,
                data,
            };
        });
    });

    let loadingJobs = $derived(series.some((s) => s.series.loading));
</script>

<div class="space-y-3">
    <div class="panel flex flex-wrap items-center gap-x-4 gap-y-2 px-3 py-2">
        <Segmented
            label="Show"
            value={source}
            options={[
                { value: 'stations', label: 'Stations' },
                { value: 'jobs', label: 'Chosen jobs' },
            ]}
            onchange={setSource}
        />
        {#if source === 'stations'}
            {#each rows as r (r.rts.id)}
                <label class="flex items-center gap-1.5 text-[13px]">
                    <input type="checkbox" checked={!hidden.includes(r.rts.id)} onchange={() => toggle(r.rts.id)} />
                    <span class="h-3 w-1 rounded-sm" style="background: {r.color}"></span>
                    <span class="font-semibold">{r.rts.name}</span>
                    <span class="text-xs text-muted">{status(r)}</span>
                </label>
            {/each}
        {:else}
            <Button size="sm" icon="plus" onclick={() => (pickerOpen = true)}>{selection.length ? 'Add or remove' : 'Choose measurements'}</Button>
            {#if selection.length}<button class="text-xs text-muted hover:text-fg" onclick={() => select([])}>Clear</button>{/if}
        {/if}
        <span class="ml-auto flex flex-wrap items-center gap-2">
            <Segmented label="Values" bind:value={mode} options={[{ value: 'position', label: 'E/N/H' }, { value: 'polar', label: 'Hz/V/D' }]} />
            {#if source === 'stations'}
                <Segmented
                    label="Time span"
                    bind:value={windowSeconds}
                    options={[
                        { value: 60, label: '1 min' },
                        { value: 600, label: '10 min' },
                        { value: 3600, label: '1 h' },
                        { value: 0, label: 'Whole job' },
                    ]}
                />
            {:else}
                <Segmented
                    label="Time axis"
                    bind:value={relative}
                    options={[
                        { value: false, label: 'Clock time' },
                        { value: true, label: 'Since start' },
                    ]}
                />
            {/if}
        </span>
    </div>

    {#if source === 'jobs' && picked.length}
        <ul class="flex flex-wrap gap-2">
            {#each picked as p (p.job.id)}
                {@const duration = p.job.first_t != null && p.job.last_t != null ? p.job.last_t - p.job.first_t : null}
                <li class="panel flex items-center gap-2 py-1 pr-1 pl-2 text-[13px]">
                    <span class="h-4 w-1 rounded-sm" style="background: {p.color}"></span>
                    <a class="font-semibold hover:text-accent" href={href(store.session?.id ?? null, 'data', p.job.id)}>{jobLabel(p.job)}</a>
                    <span class="num text-xs text-muted">{fmtShortDuration(duration)}</span>
                    {#if p.isLive}<span class="text-xs font-semibold text-good">live</span>{/if}
                    <button class="rounded p-1 text-muted hover:bg-surface-2 hover:text-fg" aria-label="Remove from plot" onclick={() => select(selection.filter((id) => id !== p.job.id))}>
                        <Icon name="x" size={13} />
                    </button>
                </li>
            {/each}
        </ul>
    {/if}

    {#if store.rts.length === 0 && source === 'stations'}
        <p class="panel px-3 py-10 text-center text-muted">No total stations in this session.</p>
    {:else if source === 'stations'}
        <PlotPanel
            traces={stationTraces}
            {mode}
            version={tick}
            follow={anyLive && windowSeconds > 0 ? windowSeconds : 0}
            title={anyLive ? 'Live' : 'Last measurements'}
            mapHeight={560}
            plotHeight={170}
        />
    {:else if selection.length === 0}
        <div class="panel px-3 py-12 text-center">
            <p class="font-semibold">Compare measurements</p>
            <p class="mt-1 text-[13px] text-muted">Choose up to {MAX_JOBS} measurements of this session to plot them together, on clock time or aligned at their start.</p>
            <Button variant="primary" icon="plus" class="mt-4" onclick={() => (pickerOpen = true)}>Choose measurements</Button>
        </div>
    {:else}
        <PlotPanel
            traces={jobTraces}
            {mode}
            {relative}
            version={jobTick + (relative ? 1_000_000 : 0)}
            title={relative ? 'Measurements (time since their start)' : 'Measurements'}
            empty={loadingJobs || picked.length < selection.length ? 'Loading …' : 'No measurements to show.'}
            mapHeight={560}
            plotHeight={170}
        />
    {/if}
</div>

<JobPicker bind:open={pickerOpen} selected={selection} max={MAX_JOBS} onapply={select} />
