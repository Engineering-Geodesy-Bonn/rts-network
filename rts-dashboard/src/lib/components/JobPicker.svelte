<!-- Dialog to choose measurements (jobs with data) of the session for plotting. -->
<script lang="ts">
    import { api } from '../api';
    import { fmtCount, fmtDateTime, fmtShortDuration, JOB_TYPE_LABEL, rtsColor } from '../format';
    import { store } from '../store.svelte';
    import type { Job } from '../types';
    import { MEASURING_TYPES } from '../types';
    import Button from './ui/Button.svelte';
    import Modal from './ui/Modal.svelte';

    let {
        open = $bindable(false),
        selected,
        max,
        onapply,
    }: { open?: boolean; selected: string[]; max: number; onapply: (ids: string[]) => void } = $props();

    let jobs = $state<Job[]>([]);
    let chosen = $state<string[]>([]);
    let station = $state('');
    let loading = $state(false);
    let error = $state('');

    $effect(() => {
        if (!open || !store.session) return;
        chosen = [...selected];
        loading = true;
        api.jobs({ session_id: store.session.id, type: MEASURING_TYPES, with_measurements: true, limit: 500 })
            .then((page) => ((jobs = page.items), (error = '')))
            .catch((e) => (error = e.message))
            .finally(() => (loading = false));
    });

    let list = $derived(station ? jobs.filter((j) => j.rts_id === station) : jobs);

    function toggle(id: string) {
        if (chosen.includes(id)) chosen = chosen.filter((c) => c !== id);
        else if (chosen.length < max) chosen = [...chosen, id];
    }

    function apply() {
        onapply(chosen);
        open = false;
    }
</script>

<Modal bind:open title="Choose measurements to plot" wide>
    <div class="mb-3 flex flex-wrap items-center gap-3">
        <select class="!w-auto !py-1" bind:value={station} aria-label="Station">
            <option value="">All stations</option>
            {#each store.rts as r (r.id)}<option value={r.id}>{r.name}</option>{/each}
        </select>
        <span class="text-xs text-muted">{chosen.length} of at most {max} selected</span>
        {#if chosen.length}<button class="ml-auto text-xs text-muted hover:text-fg" onclick={() => (chosen = [])}>Clear selection</button>{/if}
    </div>
    {#if error}<p class="rounded-[5px] bg-bad-soft px-3 py-2 text-bad">{error}</p>{/if}
    <div class="max-h-[55dvh] overflow-y-auto rounded-[5px] border border-line">
        <table class="data-table">
            <tbody>
                {#each list as job (job.id)}
                    {@const index = store.rtsIndex(job.rts_id)}
                    {@const on = chosen.includes(job.id)}
                    {@const duration = job.first_t != null && job.last_t != null ? job.last_t - job.first_t : null}
                    <tr class="link {on ? 'bg-surface-2' : ''}" onclick={() => toggle(job.id)}>
                        <td class="w-8"><input type="checkbox" checked={on} disabled={!on && chosen.length >= max} aria-label="Select" onclick={(e) => e.stopPropagation()} onchange={() => toggle(job.id)} /></td>
                        <td>
                            <span class="flex items-center gap-2">
                                <span class="h-4 w-1 rounded-sm" style="background: {index >= 0 ? rtsColor(index) : 'var(--faint)'}"></span>
                                <span class="font-semibold">{store.rtsById(job.rts_id)?.name ?? 'Removed station'}</span>
                            </span>
                        </td>
                        <td class="num">{fmtDateTime(job.first_t ?? job.created_at)}</td>
                        <td class="r num">{fmtShortDuration(duration)}</td>
                        <td class="r num">{fmtCount(job.count)}</td>
                        <td class="text-muted">{JOB_TYPE_LABEL[job.type]}{#if job.status === 'running'} · <span class="text-good">live</span>{/if}</td>
                        <td class="max-w-48 truncate text-muted" title={job.note}>{job.note}</td>
                    </tr>
                {:else}
                    <tr><td class="py-8 text-center text-muted">{loading ? 'Loading …' : 'No measurements in this session.'}</td></tr>
                {/each}
            </tbody>
        </table>
    </div>
    {#snippet footer()}
        <Button onclick={() => (open = false)}>Cancel</Button>
        <Button variant="primary" disabled={chosen.length === 0} onclick={apply}>Plot {chosen.length || ''}</Button>
    {/snippet}
</Modal>
