<!-- Map and one time plot (quantity selectable) for one or several stations. -->
<script lang="ts" module>
    export interface Trace {
        label: string;
        color: string;
        station: { x: number; y: number } | null;
        live: boolean;
        data: Plotted | null;
    }
</script>

<script lang="ts">
    import type { Snippet } from 'svelte';
    import { clock } from '../clock.svelte';
    import { loadPref, QUANTITIES, savePref, type Plotted, type Quantity } from '../plotdata';
    import PlanPlot, { type PlanTrack } from './plots/PlanPlot.svelte';
    import TimePlot, { type TimeSeries } from './plots/TimePlot.svelte';

    let {
        traces,
        version,
        follow = 0,
        onzoom,
        controls,
    }: { traces: Trace[]; version: number; follow?: number; onzoom?: (range: [number, number] | null) => void; controls?: Snippet } = $props();

    let quantity = $state<Quantity>(loadPref('rts-quantity', 'z'));
    $effect(() => savePref('rts-quantity', quantity));
    let meta = $derived(QUANTITIES.find((q) => q.value === quantity) ?? QUANTITIES[0]);

    let tracks = $derived<PlanTrack[]>(
        traces.map((tr) => ({
            label: tr.label,
            color: tr.color,
            x: tr.data?.x ?? [],
            y: tr.data?.y ?? [],
            station: tr.station,
            current: tr.live,
            stale: !tr.live && traces.some((o) => o.live),
        })),
    );

    let series = $derived<TimeSeries[]>(
        traces
            .filter((tr) => tr.data && tr.data.t.length > 0)
            .map((tr) => {
                const values = tr.data![quantity];
                return { label: tr.label, color: tr.color, t: tr.data!.t, y: meta.scale ? values.map(meta.scale) : values };
            }),
    );
    let empty = $derived(series.length === 0);
</script>

<section class="card p-4 sm:p-5">
    <div class="mb-4 flex flex-wrap items-center gap-3">
        {@render controls?.()}
    </div>
    {#if empty}
        <p class="py-16 text-center text-muted">No measurements to show yet.</p>
    {:else}
        <div class="grid grid-cols-1 gap-5 lg:grid-cols-2 [&>*]:min-w-0">
            <div>
                <p class="mb-2 flex h-9 items-center text-sm font-medium text-muted">Map</p>
                <PlanPlot {tracks} {version} height={380} />
            </div>
            <div>
                <select class="mb-2 h-9 !w-auto !py-1 text-sm" bind:value={quantity} aria-label="Quantity">
                    {#each QUANTITIES as q (q.value)}<option value={q.value}>{q.label} over time</option>{/each}
                </select>
                <TimePlot {series} {version} yLabel={meta.unit} height={380} {follow} now={() => clock.server} {onzoom} />
            </div>
        </div>
    {/if}
</section>
