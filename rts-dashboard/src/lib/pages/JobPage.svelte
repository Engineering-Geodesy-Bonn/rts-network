<script lang="ts">
    import { onMount } from 'svelte';
    import { api, download } from '../api';
    import DelayCalibration from '../components/DelayCalibration.svelte';
    import PlotPanel, { type Trace } from '../components/PlotPanel.svelte';
    import Button from '../components/ui/Button.svelte';
    import Icon from '../components/ui/Icon.svelte';
    import Panel from '../components/ui/Panel.svelte';
    import Segmented from '../components/ui/Segmented.svelte';
    import Tag from '../components/ui/Tag.svelte';
    import { confirm } from '../confirm.svelte';
    import { fmtCount, JOB_STATUS_LABEL, JOB_TYPE_LABEL, jobPrism, rtsColor, settingsRows } from '../format';
    import { live, type Columns } from '../live.svelte';
    import { loadPref, savePref, thin } from '../plotdata';
    import { href, navigate } from '../router.svelte';
    import { store } from '../store.svelte';
    import { toast } from '../toast.svelte';
    import type { Job, RTS } from '../types';
    import { ACTIVE_STATUSES, MEASURING_TYPES, TRACKING_TYPES } from '../types';

    let { jobId }: { jobId: string } = $props();

    let job = $state<Job | null>(null);
    let error = $state('');
    let note = $state('');
    let busy = $state('');
    let detail = $state.raw<Columns | null>(null);
    let mode = $state<'position' | 'polar'>(loadPref('rts-mode', 'position'));
    $effect(() => savePref('rts-mode', mode));

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
    // A removed station is not in the store, but its jobs still have their measurements
    let removedRts = $state<RTS | null>(null);
    $effect(() => {
        const id = job?.rts_id;
        if (!id || store.rtsById(id) || removedRts?.id === id) return;
        api.rts(id).then((r) => (removedRts = r)).catch(() => {});
    });
    let rts = $derived(store.rtsById(job?.rts_id) ?? (removedRts && removedRts.id === job?.rts_id ? removedRts : undefined));
    let removed = $derived(!!rts && !store.rtsById(rts.id));
    // What the job ran with; the current station settings only for jobs without a record
    let used = $derived(job?.settings ?? rts ?? null);
    let color = $derived(rtsColor(Math.max(0, store.rtsIndex(job?.rts_id))));
    let duration = $derived(job?.first_t != null && job.last_t != null ? job.last_t - job.first_t : null);

    let version = $derived((series?.version ?? 0) + (detail ? 1_000_000 : 0));
    let traces = $derived.by<Trace[]>(() => {
        void version;
        if (!rts || !series || (!detail && series.cols.t.length === 0)) return [];
        const ranges = detail ? [{ cols: detail, from: 0, to: detail.t.length }] : series.whole();
        return [{ label: rts.name, color, station: { x: rts.station_x, y: rts.station_y }, live: isLive, data: thin(ranges, 5000) }];
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

    const pad = (v: number) => String(v).padStart(2, '0');
    function stamp(epoch: number | null | undefined): string {
        if (epoch == null) return '–';
        const d = new Date(epoch * 1000);
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${String(d.getMilliseconds()).padStart(3, '0')}`;
    }
    function hms(seconds: number | null): string {
        if (seconds == null) return '–';
        const s = Math.round(seconds);
        return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
    }
</script>

<a href={href(store.session?.id ?? null, 'data')} class="mb-3 inline-flex items-center gap-1 text-[13px] text-muted hover:text-fg"><Icon name="chevronLeft" size={15} /> Measurements</a>

{#if error}
    <p class="rounded-[5px] bg-bad-soft px-3 py-2 text-bad">{error}</p>
{:else if job}
    <div class="space-y-3">
        <div class="flex flex-wrap items-center gap-3">
            <span class="h-6 w-1 rounded-sm" style="background: {color}"></span>
            <h1 class="text-[17px] font-semibold">{rts ? `${rts.name}${removed ? ' (removed)' : ''}` : 'Removed station'} · {JOB_TYPE_LABEL[job.type]}</h1>
            <Tag tone={job.status === 'running' ? 'good' : job.status === 'failed' || job.status === 'lost' ? 'bad' : job.status === 'interrupted' ? 'warn' : 'neutral'} text={JOB_STATUS_LABEL[job.status]} />
            <span class="ml-auto flex flex-wrap gap-2">
                {#if active}<Button variant="stop" icon="stop" onclick={() => store.stopJob(job!)}>Stop</Button>{/if}
                {#if measured && job.count > 0}
                    <Button variant="primary" icon="download" busy={busy === 'corrected'} disabled={busy !== ''} onclick={() => get('corrected')}>Corrected CSV</Button>
                    <Button icon="download" busy={busy === 'trajectory'} disabled={busy !== ''} onclick={() => get('trajectory')}>Trajectory (.traj)</Button>
                    <Button icon="download" busy={busy === 'raw'} disabled={busy !== ''} onclick={() => get('raw')}>Raw CSV</Button>
                    <Button icon="layers" href={href(store.session?.id ?? null, 'plot', job.id)} title="Plot this measurement together with others">Compare</Button>
                {/if}
            </span>
        </div>

        {#if job.error}
            <p class="rounded-[5px] border border-bad/40 bg-bad-soft px-3 py-2 text-[13px] text-bad">{job.error}</p>
        {/if}

        <Panel title="Details" flush>
            <dl class="grid grid-cols-2 gap-px bg-line sm:grid-cols-4 lg:grid-cols-6 [&>div]:bg-surface [&>div]:px-3 [&>div]:py-2">
                <div><dt class="label">First measurement</dt><dd class="num">{stamp(job.first_t)}</dd></div>
                <div><dt class="label">Last measurement</dt><dd class="num">{stamp(job.last_t)}</dd></div>
                <div><dt class="label">Duration</dt><dd class="num">{hms(duration)}</dd></div>
                <div><dt class="label">Points</dt><dd class="num">{fmtCount(job.count)}</dd></div>
                <div><dt class="label">Mean rate [Hz]</dt><dd class="num">{duration && duration > 1 ? ((job.count - 1) / duration).toFixed(2) : '–'}</dd></div>
                <div><dt class="label">Created</dt><dd class="num">{stamp(job.created_at)}</dd></div>
                <div><dt class="label">Prism</dt><dd>{jobPrism(job)}</dd></div>
                <div><dt class="label">Station E / N / H [m]</dt><dd class="num">{used ? `${used.station_x.toFixed(3)} / ${used.station_y.toFixed(3)} / ${used.station_z.toFixed(3)}` : '–'}</dd></div>
                <div><dt class="label">Port</dt><dd class="num truncate">{used?.port ?? '–'}</dd></div>
                <div><dt class="label">Delays int / ext [ms]</dt><dd class="num">{used ? `${(used.internal_delay * 1000).toFixed(2)} / ${(used.external_delay * 1000).toFixed(2)}` : '–'}</dd></div>
                <div><dt class="label">Worker</dt><dd class="num truncate">{job.worker_id ?? '–'}</dd></div>
                <div class="col-span-2"><dt class="label">Job ID</dt><dd class="num truncate">{job.id}</dd></div>
            </dl>
            {#if job.settings}
                <details class="group border-t border-line">
                    <summary class="label cursor-pointer px-3 py-2 group-open:!text-fg">All settings used (recorded {stamp(job.settings.recorded_at)})</summary>
                    <dl class="grid grid-cols-1 gap-px bg-line sm:grid-cols-2 lg:grid-cols-3 [&>div]:bg-surface [&>div]:px-3 [&>div]:py-2">
                        {#each settingsRows(job.settings) as [name, value] (name)}<div><dt class="label">{name}</dt><dd class="num">{value}</dd></div>{/each}
                    </dl>
                </details>
            {:else if job.status !== 'pending'}
                <p class="border-t border-line px-3 py-2 text-xs text-muted">The settings of this job were not recorded (it ran before this feature); the values above are the current station settings.</p>
            {/if}
        </Panel>

        {#if measured}
            <PlotPanel {traces} {version} {mode} onzoom={zoom} title={isLive ? 'Measurements (live)' : 'Measurements'}>
                {#snippet controls()}
                    {#if !isLive}<span class="text-xs text-muted">Drag in a time plot to zoom to full resolution</span>{/if}
                    <Segmented label="Values" bind:value={mode} options={[{ value: 'position', label: 'E/N/H' }, { value: 'polar', label: 'Hz/V/D' }]} />
                {/snippet}
            </PlotPanel>
        {/if}

        {#if !active && !removed && TRACKING_TYPES.includes(job.type) && job.count >= 30}
            <DelayCalibration {job} {rts} />
        {/if}

        <Panel title="Note">
            <textarea rows="2" bind:value={note} onblur={saveNote} placeholder="What was measured? Saved when you leave the field."></textarea>
        </Panel>

        {#if !active}
            <div class="text-right"><Button variant="danger" icon="trash" onclick={remove}>Delete measurement</Button></div>
        {/if}
    </div>
{:else}
    <div class="mt-16 flex justify-center"><span class="h-5 w-5 animate-spin rounded-full border-2 border-faint border-t-transparent"></span></div>
{/if}
