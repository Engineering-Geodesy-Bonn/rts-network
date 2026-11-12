<!--
    Estimates the internal delay of a total station from a measurement with a prism moving
    on a circle (extended sphere fit in the API) and stores it for the station on request.
-->
<script lang="ts">
    import { api } from '../api';
    import { fmtCount } from '../format';
    import { store } from '../store.svelte';
    import { toast } from '../toast.svelte';
    import type { InternalDelayEstimate, Job, RTS } from '../types';
    import TimePlot, { type TimeSeries } from './plots/TimePlot.svelte';
    import Button from './ui/Button.svelte';
    import Panel from './ui/Panel.svelte';

    let { job, rts }: { job: Job; rts: RTS | undefined } = $props();

    const BEFORE = '#e8590c';
    const AFTER = '#2b9a3e';

    let estimate = $state.raw<InternalDelayEstimate | null>(null);
    let error = $state('');
    let busy = $state<'' | 'estimate' | 'apply'>('');

    const ms = (seconds: number, digits = 3) => (seconds * 1000).toFixed(digits);
    const mm = (metres: number) => (metres * 1000).toFixed(2);

    let series = $derived<TimeSeries[]>(
        estimate
            ? [
                  { label: 'Without delay', color: BEFORE, t: estimate.residuals.t, y: estimate.residuals.before.map((v) => v * 1000) },
                  { label: 'With estimated delay', color: AFTER, t: estimate.residuals.t, y: estimate.residuals.after.map((v) => v * 1000) },
              ]
            : [],
    );
    // the station may have been edited since the estimate was computed
    let current = $derived(rts?.internal_delay ?? estimate?.current_internal_delay ?? 0);
    let isSet = $derived(!!estimate && Math.abs(current - estimate.internal_delay) < 1e-9);

    async function run(apply: boolean) {
        busy = apply ? 'apply' : 'estimate';
        error = '';
        try {
            const result = await api.internalDelay(job.id, apply);
            estimate = result;
            if (apply) {
                const index = store.rts.findIndex((r) => r.id === result.rts_id);
                if (index >= 0) store.rts[index].internal_delay = result.internal_delay;
                toast.ok(`Instrument delay of ${rts?.name ?? 'the station'} set to ${ms(result.internal_delay)} ms`);
            }
        } catch (e) {
            if (apply) toast.error((e as Error).message);
            else error = (e as Error).message;
        } finally {
            busy = '';
        }
    }
</script>

<Panel title="Instrument delay calibration">
    {#snippet actions()}
        <Button busy={busy === 'estimate'} disabled={busy !== ''} onclick={() => run(false)}>{estimate ? 'Estimate again' : 'Estimate delay'}</Button>
    {/snippet}

    {#if !estimate}
        <p class="text-[13px] text-muted">
            If the prism moved on a circle around a fixed point during this measurement (e.g. on a rotating arm), the delay between the angle and the distance measurement of the instrument can be
            estimated from it with a sphere fit. Nothing is changed until you apply the result.
        </p>
        {#if error}<p class="mt-2 rounded-[5px] border border-bad/40 bg-bad-soft px-3 py-2 text-[13px] text-bad">{error}</p>{/if}
    {:else}
        <dl class="grid grid-cols-2 gap-px overflow-hidden rounded-[5px] border border-line bg-line sm:grid-cols-3 lg:grid-cols-6 [&>div]:bg-surface [&>div]:px-3 [&>div]:py-2">
            <div><dt class="label">Estimated delay [ms]</dt><dd class="num text-[15px] font-semibold">{ms(estimate.internal_delay)} <span class="text-xs font-normal text-muted">± {ms(estimate.sigma)}</span></dd></div>
            <div><dt class="label">Currently set [ms]</dt><dd class="num">{ms(current)}</dd></div>
            <div><dt class="label">Deviation from sphere [mm]</dt><dd class="num">{mm(estimate.rms_before)} → {mm(estimate.rms_after)}</dd></div>
            <div><dt class="label">Radius [m]</dt><dd class="num">{estimate.radius.toFixed(4)} <span class="text-xs text-muted">± {mm(estimate.sigma_radius)} mm</span></dd></div>
            <div><dt class="label">Points used</dt><dd class="num">{fmtCount(estimate.points_used)} / {fmtCount(estimate.points_total)}</dd></div>
            <div><dt class="label">Variance factor</dt><dd class="num">{estimate.variance_factor.toFixed(2)}</dd></div>
        </dl>

        {#each estimate.warnings as warning (warning)}
            <p class="mt-2 rounded-[5px] border border-warn/40 bg-warn-soft px-3 py-2 text-[13px] text-warn">{warning}</p>
        {/each}
        {#if error}<p class="mt-2 rounded-[5px] border border-bad/40 bg-bad-soft px-3 py-2 text-[13px] text-bad">{error}</p>{/if}

        <div class="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
            <span class="label">Distance to the fitted sphere</span>
            <span class="flex items-center gap-1.5"><span class="h-0.5 w-4" style="background: {BEFORE}"></span>without delay</span>
            <span class="flex items-center gap-1.5"><span class="h-0.5 w-4" style="background: {AFTER}"></span>with estimated delay</span>
        </div>
        <TimePlot {series} yLabel="Deviation [mm]" height={200} />

        <div class="mt-3 flex flex-wrap items-center justify-end gap-3">
            <span class="text-xs text-muted">
                {#if !rts}The station was removed, the delay cannot be stored.
                {:else if isSet}This delay is set for {rts.name}.
                {:else}Applies to the corrected exports of all measurements of {rts.name}.{/if}
            </span>
            <Button variant="primary" busy={busy === 'apply'} disabled={busy !== '' || !rts || isSet || !estimate.converged} onclick={() => run(true)}>
                Set {ms(estimate.internal_delay)} ms for {rts?.name ?? 'station'}
            </Button>
        </div>
    {/if}
</Panel>
