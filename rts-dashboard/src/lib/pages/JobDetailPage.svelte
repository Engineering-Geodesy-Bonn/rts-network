<script lang="ts">
    import { onMount } from 'svelte';
    import { api, download } from '../api';
    import PlanPlot, { type PlanTrack } from '../components/plots/PlanPlot.svelte';
    import TimePlot from '../components/plots/TimePlot.svelte';
    import Badge from '../components/ui/Badge.svelte';
    import Button from '../components/ui/Button.svelte';
    import Icon from '../components/ui/Icon.svelte';
    import { confirm } from '../confirm.svelte';
    import { fmtCount, fmtDateTime, fmtDuration, JOB_STATUS_LABEL, JOB_STATUS_TONE, JOB_TYPE_LABEL, rtsColor, units } from '../format';
    import { live, type Columns } from '../live.svelte';
    import { href, navigate } from '../router.svelte';
    import { store } from '../store.svelte';
    import { toast } from '../toast.svelte';
    import type { Job } from '../types';
    import { ACTIVE_STATUSES, MEASURING_TYPES, TRACKING_TYPES } from '../types';

    let { jobId }: { jobId: string } = $props();

    let job = $state<Job | null>(null);
    let error = $state('');
    let note = $state('');
    let savingNote = $state(false);
    let busy = $state('');
    let quantity = $state<'xyz' | 'polar'>('xyz');
    let detail = $state.raw<Columns | null>(null);
    let detailStride = $state(1);

    onMount(async () => {
        try {
            job = await api.job(jobId);
            note = job.note;
        } catch (e) {
            error = (e as Error).message;
        }
    });

    // live updates of this job
    $effect(() => {
        const event = store.lastJobEvent;
        if (event && event.id === jobId) job = event;
    });

    let isLive = $derived(!!job && ACTIVE_STATUSES.includes(job.status) && TRACKING_TYPES.includes(job.type));
    let measuring = $derived(!!job && MEASURING_TYPES.includes(job.type));
    let series = $derived(job && measuring && job.count + (isLive ? 1 : 0) > 0 ? live.get(job, isLive) : undefined);
    let rts = $derived(store.rtsById(job?.rts_id));
    let color = $derived(rtsColor(Math.max(0, store.rtsIndex(job?.rts_id))));
    let cols = $derived.by(() => {
        void series?.version;
        return detail ?? series?.cols ?? null;
    });
    let version = $derived((series?.version ?? 0) + (detail ? 1e6 : 0));
    let stride = $derived(detail ? detailStride : (series?.stride ?? 1));

    async function zoom(range: [number, number] | null) {
        if (!range || !series || isLive) {
            detail = null;
            return;
        }
        // load full resolution for the selected time range
        const c = series.cols;
        const from = c.seq[Math.max(0, series.indexAt(range[0]) - 1)];
        const to = c.seq[Math.min(c.seq.length - 1, series.indexAt(range[1]))];
        try {
            const data = await api.measurements(jobId, { from_seq: from, to_seq: to, max_points: 20000 });
            detail = data;
            detailStride = data.stride;
        } catch (e) {
            toast.error((e as Error).message);
        }
    }

    let plots = $derived(
        cols
            ? quantity === 'xyz'
                ? [
                      { key: 'x', label: 'Easting (m)', y: cols.x },
                      { key: 'y', label: 'Northing (m)', y: cols.y },
                      { key: 'z', label: 'Height (m)', y: cols.z },
                  ]
                : [
                      { key: 'hz', label: 'Hz (gon)', y: cols.hz.map(units.radToGon) },
                      { key: 'v', label: 'V (gon)', y: cols.v.map(units.radToGon) },
                      { key: 'd', label: 'Distance (m)', y: cols.d },
                  ]
            : [],
    );

    let tracks = $derived<PlanTrack[]>(
        cols && rts
            ? [{ label: rts.name, color, x: cols.x, y: cols.y, station: { x: rts.station_x, y: rts.station_y }, current: isLive, stale: false }]
            : [],
    );

    async function saveNote() {
        if (!job) return;
        savingNote = true;
        try {
            job = await api.updateJob(job.id, note);
            toast.ok('Note saved');
        } catch (e) {
            toast.error((e as Error).message);
        } finally {
            savingNote = false;
        }
    }

    async function get(kind: 'raw' | 'corrected' | 'trajectory') {
        busy = kind;
        try {
            const path = kind === 'trajectory' ? `/jobs/${jobId}/trajectory` : `/jobs/${jobId}/csv?corrected=${kind === 'corrected'}`;
            const name = await download(path, `${jobId}.${kind === 'trajectory' ? 'traj' : 'csv'}`);
            toast.ok(`Downloaded ${name}`);
        } catch (e) {
            toast.error((e as Error).message);
        } finally {
            busy = '';
        }
    }

    async function remove() {
        if (!job) return;
        const ok = await confirm({
            title: 'Delete this job?',
            message: `The job and its ${fmtCount(job.count)} measurements are deleted permanently. Download them first if you still need them.`,
            confirm: 'Delete',
            danger: true,
        });
        if (!ok) return;
        try {
            await api.deleteJob(job.id);
            toast.ok('Job deleted');
            navigate(href(store.session!.id, 'jobs'));
        } catch (e) {
            toast.error((e as Error).message);
        }
    }

    async function stop() {
        if (job) await store.stopJob(job);
    }
</script>

<a href={href(store.session?.id ?? null, 'jobs')} class="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-fg"><Icon name="chevronLeft" size={16} /> History</a>

{#if error}
    <p class="rounded-lg bg-fail-bg p-4 text-sm text-fail">{error}</p>
{:else if job}
    <div class="mb-4 flex flex-wrap items-start gap-3">
        <div class="mr-auto min-w-0">
            <h1 class="flex items-center gap-2.5 text-xl font-bold">
                <span class="h-3 w-3 rounded-full" style="background: {color}"></span>
                {JOB_TYPE_LABEL[job.type]} · {rts?.name ?? 'removed station'}
            </h1>
            <p class="mt-1 text-sm text-muted">
                {fmtDateTime(job.started_at ?? job.created_at)}
                {#if job.first_t != null && job.last_t != null} · {fmtDuration(job.last_t - job.first_t)}{/if}
                · {fmtCount(job.count)} measurements
                {#if job.first_t != null && job.last_t != null && job.last_t > job.first_t} · {((job.count - 1) / (job.last_t - job.first_t)).toFixed(1)} Hz{/if}
            </p>
        </div>
        <Badge tone={JOB_STATUS_TONE[job.status]} pulse={job.status === 'running'}>{JOB_STATUS_LABEL[job.status]}</Badge>
    </div>

    {#if job.error}
        <p class="mb-4 flex items-start gap-2 rounded-lg bg-fail-bg p-3 text-sm text-fail"><Icon name="alert" class="mt-0.5" />{job.error}</p>
    {/if}

    <div class="mb-4 flex flex-wrap items-center gap-2">
        {#if ACTIVE_STATUSES.includes(job.status)}
            <Button variant="danger" icon="stop" onclick={stop} disabled={job.stop_requested && job.status === 'running'}>Stop</Button>
        {/if}
        {#if measuring && job.count > 0}
            <Button icon="download" busy={busy === 'raw'} onclick={() => get('raw')}>Raw CSV</Button>
            <Button icon="download" busy={busy === 'corrected'} onclick={() => get('corrected')}>Corrected CSV</Button>
            <Button icon="download" busy={busy === 'trajectory'} onclick={() => get('trajectory')}>Trajectory</Button>
        {/if}
        {#if !ACTIVE_STATUSES.includes(job.status)}
            <Button variant="danger" icon="trash" class="ml-auto" onclick={remove}>Delete</Button>
        {/if}
    </div>

    <div class="mb-4 flex flex-col gap-2 sm:flex-row">
        <input bind:value={note} placeholder="Add a note to this job (e.g. what was measured)" maxlength="1000" />
        <Button busy={savingNote} disabled={note === job.note} onclick={saveNote}>Save note</Button>
    </div>

    {#if measuring && cols}
        <div class="mb-2 flex flex-wrap items-center gap-2">
            <div class="inline-flex rounded-lg border border-line bg-surface p-0.5" role="group">
                <button class="rounded-md px-3 py-1.5 text-sm font-medium {quantity === 'xyz' ? 'bg-accent text-accent-fg' : 'text-muted hover:text-fg'}" onclick={() => (quantity = 'xyz')}>E / N / H</button>
                <button class="rounded-md px-3 py-1.5 text-sm font-medium {quantity === 'polar' ? 'bg-accent text-accent-fg' : 'text-muted hover:text-fg'}" onclick={() => (quantity = 'polar')}>Hz / V / D</button>
            </div>
            <span class="text-xs text-muted">
                {#if stride > 1}Showing every {stride}th measurement · drag across a plot to load full resolution{:else}Full resolution{/if}
                {#if isLive} · live{/if}
            </span>
        </div>
        <section class="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] [&>*]:min-w-0">
            <div class="rounded-xl border border-line bg-surface p-3 shadow-sm">
                <PlanPlot {tracks} {version} height={420} />
            </div>
            <div class="space-y-3">
                {#each plots as p (p.key + quantity)}
                    <div class="rounded-xl border border-line bg-surface p-3 shadow-sm">
                        <TimePlot series={[{ label: rts?.name ?? '', color, t: cols.t, y: p.y }]} {version} yLabel={p.label} height={150} onzoom={zoom} />
                    </div>
                {/each}
            </div>
        </section>
    {:else if measuring && series?.loading}
        <div class="mt-10 flex justify-center"><span class="h-6 w-6 animate-spin rounded-full border-2 border-muted border-t-transparent"></span></div>
    {:else if measuring}
        <p class="text-sm text-muted">No measurements.</p>
    {/if}
{:else}
    <div class="mt-10 flex justify-center"><span class="h-6 w-6 animate-spin rounded-full border-2 border-muted border-t-transparent"></span></div>
{/if}
