<!-- Data: all jobs of the session, newest first, as a table. -->
<script lang="ts">
    import { api, download } from '../api';
    import Button from '../components/ui/Button.svelte';
    import Tag from '../components/ui/Tag.svelte';
    import { events } from '../events.svelte';
    import { fmtCount, JOB_STATUS_LABEL, JOB_TYPE_LABEL, rtsColor } from '../format';
    import { href, navigate } from '../router.svelte';
    import { store } from '../store.svelte';
    import { toast } from '../toast.svelte';
    import type { Job, JobStatus } from '../types';
    import { MEASURING_TYPES } from '../types';

    let station = $state('');
    let showAll = $state(false);
    let jobs = $state<Job[]>([]);
    let nextBefore = $state<number | null>(null);
    let nextBeforeNo = $state<number | null>(null);
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
                before_no: more ? nextBeforeNo : null,
                limit: 100,
            });
            jobs = more ? [...jobs, ...page.items] : page.items;
            nextBefore = page.next_before;
            nextBeforeNo = page.next_before_no;
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

    const pad = (v: number) => String(v).padStart(2, '0');
    function date(epoch: number): string {
        const d = new Date(epoch * 1000);
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    }
    function time(epoch: number | null | undefined): string {
        if (epoch == null) return '–';
        const d = new Date(epoch * 1000);
        return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    }
    function hms(seconds: number | null): string {
        if (seconds == null || seconds < 0) return '–';
        const s = Math.round(seconds);
        return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
    }

    const TONE: Record<JobStatus, 'good' | 'warn' | 'bad' | 'neutral' | 'accent'> = {
        pending: 'accent',
        running: 'good',
        lost: 'bad',
        finished: 'neutral',
        failed: 'bad',
        cancelled: 'neutral',
        interrupted: 'warn',
    };
</script>

<div class="mb-3 flex flex-wrap items-center gap-3">
    <h1 class="label !text-[12px] !text-fg">Measurements</h1>
    <select class="!w-auto !py-1" bind:value={station} aria-label="Station">
        <option value="">All stations</option>
        {#each store.rts as r (r.id)}<option value={r.id}>{r.name}</option>{/each}
    </select>
    <label class="flex items-center gap-1.5 text-[13px] text-muted"><input type="checkbox" bind:checked={showAll} /> Include other jobs</label>
    <span class="ml-auto"></span>
    <Button icon="download" busy={exporting} onclick={exportAll}>Export session (ZIP)</Button>
</div>

{#if error}<p class="mb-3 rounded-[5px] bg-bad-soft px-3 py-2 text-bad">{error}</p>{/if}

<div class="panel overflow-x-auto">
    <table class="data-table">
        <thead>
            <tr>
                <th>Date</th>
                <th>Start</th>
                <th>End</th>
                <th class="r">Duration</th>
                <th>Station</th>
                <th>Type</th>
                <th class="r">Points</th>
                <th class="r">Rate [Hz]</th>
                <th>Status</th>
                <th>Note</th>
            </tr>
        </thead>
        <tbody>
            {#each jobs as job (job.id)}
                {@const index = store.rtsIndex(job.rts_id)}
                {@const measured = MEASURING_TYPES.includes(job.type)}
                {@const duration = job.first_t != null && job.last_t != null ? job.last_t - job.first_t : null}
                <tr class="link" onclick={() => navigate(href(store.session!.id, 'data', job.id))}>
                    <td class="num">{date(job.started_at ?? job.created_at)}</td>
                    <td class="num">{time(job.first_t ?? job.started_at ?? job.created_at)}</td>
                    <td class="num">{time(job.last_t ?? job.finished_at)}</td>
                    <td class="r num">{measured ? hms(duration) : '–'}</td>
                    <td>
                        <span class="flex items-center gap-2">
                            <span class="h-4 w-1 rounded-sm" style="background: {index >= 0 ? rtsColor(index) : 'var(--faint)'}"></span>
                            <a href={href(store.session!.id, 'data', job.id)} class="font-semibold" onclick={(e) => e.stopPropagation()}>{store.rtsById(job.rts_id)?.name ?? 'Removed station'}</a>
                        </span>
                    </td>
                    <td class="text-muted">{JOB_TYPE_LABEL[job.type]}</td>
                    <td class="r num">{measured ? fmtCount(job.count) : '–'}</td>
                    <td class="r num">{measured && duration && duration > 1 ? ((job.count - 1) / duration).toFixed(1) : '–'}</td>
                    <td><Tag tone={TONE[job.status]} text={JOB_STATUS_LABEL[job.status]} /></td>
                    <td class="max-w-64 truncate text-muted" title={job.error ?? job.note}>{job.error && job.status !== 'finished' ? job.error : job.note}</td>
                </tr>
            {:else}
                {#if !loading}<tr><td colspan={10} class="py-10 text-center text-muted">No measurements yet.</td></tr>{/if}
            {/each}
        </tbody>
    </table>
</div>

{#if nextBefore}
    <div class="mt-3 text-center"><Button busy={loading} onclick={() => load(true)}>Load older</Button></div>
{/if}
