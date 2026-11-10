<!-- Data: all measurements of the session, newest first, grouped by day. -->
<script lang="ts">
    import { api, download } from '../api';
    import Button from '../components/ui/Button.svelte';
    import { events } from '../events.svelte';
    import { fmtClock, fmtCount, fmtShortDuration, JOB_STATUS_LABEL, JOB_TYPE_LABEL, rtsColor } from '../format';
    import { href } from '../router.svelte';
    import { store } from '../store.svelte';
    import { toast } from '../toast.svelte';
    import type { Job } from '../types';
    import { MEASURING_TYPES } from '../types';

    let station = $state('');
    let showAll = $state(false);
    let jobs = $state<Job[]>([]);
    let nextBefore = $state<number | null>(null);
    let loading = $state(false);
    let error = $state('');
    let exporting = $state(false);

    async function load(more = false) {
        if (!store.session) return;
        loading = true;
        try {
            const page = await api.jobs({
                session_id: store.session.id,
                rts_id: station || undefined,
                type: showAll ? undefined : MEASURING_TYPES,
                with_measurements: !showAll,
                before: more ? nextBefore : null,
                limit: 100,
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
        void station;
        void showAll;
        void store.session?.id;
        void load();
    });

    $effect(() => {
        const job = store.lastJobEvent;
        if (!job) return;
        const index = jobs.findIndex((j) => j.id === job.id);
        if (index >= 0) jobs[index] = job;
        else if ((!station || job.rts_id === station) && (showAll || (MEASURING_TYPES.includes(job.type) && job.count > 0))) jobs = [job, ...jobs];
    });
    $effect(() => events.onOpen((reconnect) => reconnect && void load()));

    function dayLabel(epoch: number): string {
        const date = new Date(epoch * 1000);
        const today = new Date();
        const yesterday = new Date(Date.now() - 86400000);
        if (date.toDateString() === today.toDateString()) return 'Today';
        if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
        return date.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    }

    let groups = $derived.by(() => {
        const out: { day: string; jobs: Job[] }[] = [];
        for (const job of jobs) {
            const day = dayLabel(job.started_at ?? job.created_at);
            if (out.length === 0 || out[out.length - 1].day !== day) out.push({ day, jobs: [] });
            out[out.length - 1].jobs.push(job);
        }
        return out;
    });

    async function exportAll() {
        exporting = true;
        try {
            toast.ok(`Downloaded ${await download(`/sessions/${store.session!.id}/export`, 'session.zip')}`);
        } catch (e) {
            toast.error((e as Error).message);
        } finally {
            exporting = false;
        }
    }

    function timeRange(job: Job): string {
        const start = job.first_t ?? job.started_at ?? job.created_at;
        const end = job.last_t ?? job.finished_at;
        return end && end - start > 60 ? `${fmtClock(start, false)} – ${fmtClock(end, false)}` : fmtClock(start, false);
    }
</script>

<div class="mb-6 flex flex-wrap items-center gap-3">
    <h1 class="mr-auto text-xl font-semibold">Data</h1>
    <Button icon="download" busy={exporting} onclick={exportAll}>Download everything (ZIP)</Button>
</div>

<div class="mb-5 flex flex-wrap items-center gap-4">
    <select class="!w-auto" bind:value={station} aria-label="Station">
        <option value="">All stations</option>
        {#each store.rts as r (r.id)}<option value={r.id}>{r.name}</option>{/each}
    </select>
    <label class="flex items-center gap-2 text-muted"><input type="checkbox" bind:checked={showAll} /> Also show other jobs</label>
</div>

{#if error}<p class="mb-4 rounded-lg bg-bad-soft p-3 text-bad">{error}</p>{/if}

{#if jobs.length === 0 && !loading}
    <p class="py-16 text-center text-muted">Nothing measured yet.</p>
{/if}

<div class="space-y-6">
    {#each groups as group (group.day)}
        <section>
            <h2 class="mb-2 text-sm font-semibold text-muted">{group.day}</h2>
            <ul class="card">
                {#each group.jobs as job (job.id)}
                    {@const index = store.rtsIndex(job.rts_id)}
                    {@const measured = MEASURING_TYPES.includes(job.type)}
                    <li class="border-b border-line last:border-b-0">
                        <a href={href(store.session!.id, 'data', job.id)} class="flex flex-wrap items-center gap-x-6 gap-y-1 px-5 py-3.5 hover:bg-surface-2">
                            <span class="flex min-w-44 flex-1 items-center gap-3">
                                <span class="h-8 w-1.5 shrink-0 rounded-full" style="background: {index >= 0 ? rtsColor(index) : 'var(--faint)'}"></span>
                                <span>
                                    <span class="block font-semibold">{store.rtsById(job.rts_id)?.name ?? 'Removed station'}</span>
                                    <span class="block text-sm text-muted">{JOB_TYPE_LABEL[job.type]}{job.note ? ` · ${job.note}` : ''}</span>
                                </span>
                            </span>
                            <span class="num w-32 text-muted">{timeRange(job)}</span>
                            <span class="num w-20 text-muted">{measured && job.first_t != null && job.last_t != null && job.last_t - job.first_t >= 1 ? fmtShortDuration(job.last_t - job.first_t) : ''}</span>
                            <span class="num w-32 text-right">{measured ? `${fmtCount(job.count)} points` : ''}</span>
                            <span class="w-28 text-right text-sm {job.status === 'failed' || job.status === 'lost' ? 'text-bad' : job.status === 'running' ? 'text-good' : job.status === 'interrupted' ? 'text-warn' : 'text-muted'}">
                                {job.status === 'finished' ? '' : JOB_STATUS_LABEL[job.status]}
                            </span>
                        </a>
                    </li>
                {/each}
            </ul>
        </section>
    {/each}
</div>

{#if nextBefore}
    <div class="mt-6 text-center"><Button busy={loading} onclick={() => load(true)}>Show older</Button></div>
{/if}
