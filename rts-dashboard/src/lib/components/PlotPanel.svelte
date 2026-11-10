<!-- Map and three time plots with synchronized cursors (E/N/H or Hz/V/D). -->
<script lang="ts" module>
    export interface Trace {
        label: string;
        color: string;
        station: { x: number; y: number } | null;
        live: boolean;
        data: Plotted | null;
    }

    let nextSync = 0;
</script>

<script lang="ts">
    import type { Snippet } from 'svelte';
    import { clock } from '../clock.svelte';
    import { units } from '../format';
    import type { Plotted } from '../plotdata';
    import PlanPlot, { type PlanTrack } from './plots/PlanPlot.svelte';
    import TimePlot, { type TimeSeries } from './plots/TimePlot.svelte';
    import Panel from './ui/Panel.svelte';

    let {
        traces,
        version,
        mode,
        follow = 0,
        title = 'Plots',
        mapHeight = 410,
        plotHeight = 128,
        onzoom,
        controls,
    }: {
        traces: Trace[];
        version: number;
        mode: 'position' | 'polar';
        follow?: number;
        title?: string;
        mapHeight?: number;
        plotHeight?: number;
        onzoom?: (range: [number, number] | null) => void;
        controls?: Snippet;
    } = $props();

    const syncKey = `plots-${nextSync++}`;

    const PLOTS = {
        position: [
            { key: 'x', label: 'E [m]' },
            { key: 'y', label: 'N [m]' },
            { key: 'z', label: 'H [m]' },
        ],
        polar: [
            { key: 'hz', label: 'Hz [gon]', scale: units.radToGon },
            { key: 'v', label: 'V [gon]', scale: units.radToGon },
            { key: 'd', label: 'D [m]' },
        ],
    } as const;

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

    let withData = $derived(traces.filter((tr) => tr.data && tr.data.t.length > 0));

    let plots = $derived(
        PLOTS[mode].map((p) => ({
            ...p,
            series: withData.map(
                (tr): TimeSeries => ({
                    label: tr.label,
                    color: tr.color,
                    t: tr.data!.t,
                    y: 'scale' in p ? tr.data![p.key].map(p.scale) : tr.data![p.key],
                }),
            ),
        })),
    );
</script>

<Panel {title} flush>
    {#snippet actions()}{@render controls?.()}{/snippet}
    {#if withData.length === 0}
        <p class="py-16 text-center text-muted">No measurements to show.</p>
    {:else}
        <div class="grid grid-cols-1 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] [&>*]:min-w-0">
            <div class="border-b border-line p-2 lg:border-r lg:border-b-0">
                <div class="label px-1 pb-1">Plan [E/N]</div>
                <PlanPlot {tracks} {version} height={mapHeight} />
            </div>
            <div class="p-2">
                {#each plots as p, i (p.key)}
                    <TimePlot series={p.series} {version} yLabel={p.label} height={i === plots.length - 1 ? plotHeight + 40 : plotHeight} showX={i === plots.length - 1} {syncKey} {follow} now={() => clock.server} {onzoom} />
                {/each}
            </div>
        </div>
    {/if}
</Panel>
