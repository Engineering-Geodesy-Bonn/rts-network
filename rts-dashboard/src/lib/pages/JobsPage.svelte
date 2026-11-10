<script lang="ts">
    import { api, download } from '../api';
    import Badge from '../components/ui/Badge.svelte';
    import Button from '../components/ui/Button.svelte';
    import { events } from '../events.svelte';
    import { fmtCount, fmtDateTime, fmtDuration, JOB_STATUS_LABEL, JOB_STATUS_TONE, JOB_TYPE_LABEL, rtsColor } from '../format';
    import { href } from '../router.svelte';
    import { store } from '../store.svelte';
    import { toast } from '../toast.svelte';
    import type { Job, JobStatus } from '../types';
    import { MEASURING_TYPES } from '../types';

    type Filter = 'measurements' | 'all' | 'problems';
    let filter = $state<Filter>('measurements');
    let rtsFilter = $state('');
    let jobs = $state<Job[]>([]);
    let nextBefore = $state<number | null>(null);
    let loading = $state(false);
    let error = $state('');
    let exporting = $state(false);

    const PROBLEMS: JobStatus[] = ['failed', 'interrupted', 'lost'];

    async function load(more = false) {
        if (!store.session) return;
        loading = true;
        try {
            const page = await api.jobs({
                session_id: store.session.id,
                rts_id: rtsFilter || undefined,
                type: filter === 'measurements' ? MEASURING_TYPES : undefined,
                with_measurements: filter === 'measurements',
                status: filter === 'problems' ? PROBLEMS : undefined,
                before: more ? nextBefore : null,
                limit: 50,
            });
            jobs = more ? [...jobs, ...page.items] : page.items;
            nextBefore = page.next_before;
            error = '';
        } catch (e) {
            error = (e as Error).message;
        } finally {
            loading = false;
        }
    }

    $effect(() => {
        void filter;
        void rtsFilter;
        void store.session?.id;
        void load();
    });

    // keep the list current: apply job events, reload after a reconnect
    $effect(() => {
        const job = store.lastJobEvent;
        if (!job) return;
        const index = jobs.findIndex((j) => j.id === job.id);
        if (index >= 0) jobs[index] = job;
        else if (matches(job)) jobs = [job, ...jobs];
    });
    $effect(() => events.onOpen((reconnect) => reconnect && void load()));

    function matches(job: Job): boolean {
        if (rtsFilter && job.rts_id !== rtsFilter) return false;
        if (filter === 'measurements') return MEASURING_TYPES.includes(job.type) && job.count > 0;
        if (filter === 'problems') return PROBLEMS.includes(job.status);
        return true;
    }

    async function exportSession() {
        exporting = true;
        try {
            const name = await download(`/sessions/${store.session!.id}/export`, 'session.zip');
            toast.ok(`Downloaded ${name}`);
        } catch (e) {
            toast.error((e as Error).message);
        } finally {
            exporting = false;
        }
    }
</script>

<div class="mb-4 flex flex-wrap items-center gap-2">
    <div class="mr-auto">
        <h1 class="text-xl font-bold">History</h1>
        <p class="text-sm text-muted">All jobs of this session. Open a job to inspect and download its measurements.</p>
    </div>
    <Button icon="download" busy={exporting} onclick={exportSession}>Export session (ZIP)</Button>
</div>

<div class="mb-3 flex flex-wrap items-center gap-2">
    <div class="inline-flex rounded-lg border border-line bg-surface p-0.5" role="group">
        {#each [['measurements', 'Measurements'], ['all', 'All jobs'], ['problems', 'Problems']] as [value, label] (value)}
            <button class="rounded-md px-3 py-1.5 text-sm font-medium {filter === value ? 'bg-accent text-accent-fg' : 'text-muted hover:text-fg'}" onclick={() => (filter = value as Filter)}>{label}</button>
        {/each}
    </div>
    <select class="!w-auto" bind:value={rtsFilter} aria-label="Total station">
        <option value="">All stations</option>
        {#each store.rts as r (r.id)}<option value={r.id}>{r.name}</option>{/each}
    </select>
</div>

{#if error}
    <p class="rounded-lg bg-fail-bg p-3 text-sm text-fail">{error}</p>
{/if}

<div class="overflow-hidden rounded-xl border border-line bg-surface shadow-sm">
    {#if jobs.length === 0 && !loading}
        <p class="p-8 text-center text-sm text-muted">No jobs{filter !== 'all' ? ' for this filter' : ''} yet.</p>
    {/if}
    <ul class="divide-y divide-line">
        {#each jobs as job (job.id)}
            {@const index = store.rtsIndex(job.rts_id)}
            {@const rts = store.rtsById(job.rts_id)}
            {@const duration = job.first_t != null && job.last_t != null ? job.last_t - job.first_t : null}
            <li>
                <a href={href(store.session!.id, 'jobs', job.id)} class="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-surface-2">
                    <span class="flex min-w-40 flex-1 items-center gap-2.5">
                        <span class="h-2.5 w-2.5 shrink-0 rounded-full" style="background: {index >= 0 ? rtsColor(index) : 'var(--muted)'}"></span>
                        <span class="min-w-0">
                            <span class="block truncate font-medium">{JOB_TYPE_LABEL[job.type]} · {rts?.name ?? 'removed station'}</span>
                            <span class="block text-xs text-muted">{fmtDateTime(job.started_at ?? job.created_at)}{job.note ? ` · ${job.note}` : ''}</span>
                        </span>
                    </span>
                    <span class="w-24 text-right text-sm tabular">{job.count ? fmtCount(job.count) + ' pts' : ''}</span>
                    <span class="w-24 text-right text-sm tabular text-muted">{duration ? fmtDuration(duration) : ''}</span>
                    <span class="w-28 text-right"><Badge tone={JOB_STATUS_TONE[job.status]} pulse={job.status === 'running'}>{JOB_STATUS_LABEL[job.status]}</Badge></span>
                </a>
                {#if job.error && (job.status === 'failed' || job.status === 'interrupted')}
                    <p class="px-4 pb-3 pl-9 text-xs text-fail">{job.error}</p>
                {/if}
            </li>
        {/each}
    </ul>
    {#if nextBefore || loading}
        <div class="border-t border-line p-3 text-center">
            <Button size="sm" busy={loading} onclick={() => load(true)}>Load older jobs</Button>
        </div>
    {/if}
</div>
