<script lang="ts">
    import { onMount } from 'svelte';
    import { api, download } from '../api';
    import PlotPanel, { type Trace } from '../components/PlotPanel.svelte';
    import Button from '../components/ui/Button.svelte';
    import Icon from '../components/ui/Icon.svelte';
    import { confirm } from '../confirm.svelte';
    import { fmtCount, fmtDateTime, fmtShortDuration, JOB_STATUS_LABEL, JOB_TYPE_LABEL, rtsColor } from '../format';
    import { live, type Columns } from '../live.svelte';
    import { thin } from '../plotdata';
    import { href, navigate } from '../router.svelte';
    import { store } from '../store.svelte';
    import { toast } from '../toast.svelte';
    import type { Job } from '../types';
    import { ACTIVE_STATUSES, MEASURING_TYPES, TRACKING_TYPES } from '../types';

    let { jobId }: { jobId: string } = $props();

    let job = $state<Job | null>(null);
    let error = $state('');
    let note = $state('');
    let busy = $state('');
    let detail = $state.raw<Columns | null>(null);
    onMount(() => {
        api.job(jobId)
            .then((j) => ((job = j), (note = j.note)))
            .catch((e) => (error = e.message));
    });

    $effect(() => {
        const event = store.lastJobEvent;
        if (event?.id === jobId) job = event;
    });

    let active = $derived(!!job && ACTIVE_STATUSES.includes(job.status));
    let isLive = $derived(!!job && active && TRACKING_TYPES.includes(job.type));
    let measured = $derived(!!job && MEASURING_TYPES.includes(job.type));
    let series = $derived(job && measured && (job.count > 0 || isLive) ? live.get(job, isLive) : undefined);
    let rts = $derived(store.rtsById(job?.rts_id));
    let color = $derived(rtsColor(Math.max(0, store.rtsIndex(job?.rts_id))));
    let duration = $derived(job?.first_t != null && job.last_t != null ? job.last_t - job.first_t : null);

    let version = $derived((series?.version ?? 0) + (detail ? 1_000_000 : 0));
    let traces = $derived.by<Trace[]>(() => {
        void version;
        const cols = detail ?? series?.cols;
        if (!cols || !rts) return [];
        return [{ label: rts.name, color, station: { x: rts.station_x, y: rts.station_y }, live: isLive, data: thin([{ cols, from: 0, to: cols.t.length }], 5000) }];
    });

    async function zoom(range: [number, number] | null) {
        if (!range || !series || isLive) {
            detail = null;
            return;
        }
        const c = series.cols;
        const from = c.seq[Math.max(0, series.indexAt(range[0]) - 1)];
        const to = c.seq[Math.min(c.seq.length - 1, series.indexAt(range[1]))];
        try {
            detail = await api.measurements(jobId, { from_seq: from, to_seq: to, max_points: 5000 });
        } catch (e) {
            toast.error((e as Error).message);
        }
    }

    async function get(kind: 'corrected' | 'raw' | 'trajectory') {
        busy = kind;
        try {
            const path = kind === 'trajectory' ? `/jobs/${jobId}/trajectory` : `/jobs/${jobId}/csv?corrected=${kind === 'corrected'}`;
            toast.ok(`Downloaded ${await download(path, `${jobId}.${kind === 'trajectory' ? 'traj' : 'csv'}`)}`);
        } catch (e) {
            toast.error((e as Error).message);
        } finally {
            busy = '';
        }
    }

    async function saveNote() {
        if (!job || note === job.note) return;
        try {
            job = await api.updateJob(job.id, note);
            toast.ok('Note saved');
        } catch (e) {
            toast.error((e as Error).message);
        }
    }

    async function remove() {
        if (!job) return;
        const ok = await confirm({
            title: 'Delete this measurement?',
            message: `${fmtCount(job.count)} measurements are deleted permanently. Download them first if you still need them.`,
            confirm: 'Delete',
            danger: true,
        });
        if (!ok) return;
        try {
            await api.deleteJob(job.id);
            navigate(href(store.session!.id, 'data'));
        } catch (e) {
            toast.error((e as Error).message);
        }
    }
</script>

<a href={href(store.session?.id ?? null, 'data')} class="mb-4 inline-flex items-center gap-1 text-muted hover:text-fg"><Icon name="chevronLeft" size={18} /> Data</a>

{#if error}
    <p class="rounded-lg bg-bad-soft p-4 text-bad">{error}</p>
{:else if job}
    <div class="space-y-6">
        <header class="flex items-start gap-3">
            <span class="mt-1.5 h-9 w-1.5 shrink-0 rounded-full" style="background: {color}"></span>
            <div>
                <h1 class="text-2xl font-semibold">{rts?.name ?? 'Removed station'} · {JOB_TYPE_LABEL[job.type]}</h1>
                <p class="num mt-1 text-muted">
                    {fmtDateTime(job.started_at ?? job.created_at)}
                    {#if measured}
                        <span class="mx-1 text-faint">·</span>{fmtCount(job.count)} points
                        {#if duration && duration >= 1}<span class="mx-1 text-faint">·</span>{fmtShortDuration(duration)}<span class="mx-1 text-faint">·</span>{((job.count - 1) / duration).toFixed(0)} Hz{/if}
                    {/if}
                </p>
            </div>
        </header>

        {#if job.status !== 'finished'}
            <div class="flex flex-wrap items-center gap-3 rounded-xl px-4 py-3 {job.status === 'running' ? 'bg-good-soft text-good' : job.status === 'failed' || job.status === 'lost' ? 'bg-bad-soft text-bad' : 'bg-surface-2'}">
                <span class="font-semibold">{JOB_STATUS_LABEL[job.status]}</span>
                {#if job.error}<span>{job.error}</span>{/if}
                {#if active}<Button variant="stop" size="sm" class="ml-auto" onclick={() => store.stopJob(job!)}>Stop</Button>{/if}
            </div>
        {/if}

        {#if measured && job.count > 0}
            <section class="card p-5">
                <h2 class="mb-3 text-lg font-semibold">Download</h2>
                <div class="grid gap-3 sm:grid-cols-3">
                    <button class="rounded-xl border border-line p-4 text-left hover:bg-surface-2 disabled:opacity-50" disabled={busy !== ''} onclick={() => get('corrected')}>
                        <span class="flex items-center gap-2 font-semibold"><Icon name="download" size={18} /> Corrected CSV</span>
                        <span class="mt-1 block text-sm text-muted">Recommended. Synchronized timestamps, delays corrected.</span>
                    </button>
                    <button class="rounded-xl border border-line p-4 text-left hover:bg-surface-2 disabled:opacity-50" disabled={busy !== ''} onclick={() => get('trajectory')}>
                        <span class="flex items-center gap-2 font-semibold"><Icon name="download" size={18} /> Trajectory</span>
                        <span class="mt-1 block text-sm text-muted">Positions for trajectopy (.traj).</span>
                    </button>
                    <button class="rounded-xl border border-line p-4 text-left hover:bg-surface-2 disabled:opacity-50" disabled={busy !== ''} onclick={() => get('raw')}>
                        <span class="flex items-center gap-2 font-semibold"><Icon name="download" size={18} /> Raw CSV</span>
                        <span class="mt-1 block text-sm text-muted">As recorded by the instrument.</span>
                    </button>
                </div>
                {#if busy}<p class="mt-3 text-sm text-muted">Preparing the file…</p>{/if}
            </section>
        {/if}

        {#if measured}
            <PlotPanel {traces} {version} onzoom={zoom}>
                {#snippet controls()}
                    <h2 class="mr-auto text-lg font-semibold">Measurements</h2>
                    <span class="text-sm text-muted">{isLive ? 'Live' : 'Drag across the plot over time to zoom in'}</span>
                {/snippet}
            </PlotPanel>
        {/if}

        <section class="card p-5">
            <label for="note" class="mb-2 block text-lg font-semibold">Note</label>
            <textarea id="note" rows="2" bind:value={note} onblur={saveNote} placeholder="What was measured? (saved automatically)"></textarea>
        </section>

        {#if !active}
            <div class="text-right"><Button variant="danger" icon="trash" onclick={remove}>Delete this measurement</Button></div>
        {/if}
    </div>
{:else}
    <div class="mt-16 flex justify-center"><span class="h-6 w-6 animate-spin rounded-full border-2 border-faint border-t-transparent"></span></div>
{/if}
