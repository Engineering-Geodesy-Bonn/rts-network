<!--
    Plot: map and time plots of the selected stations. Running jobs are shown live,
    idle stations with their last measurement.
-->
<script lang="ts">
    import { clock } from '../clock.svelte';
    import PlotPanel, { type Trace } from '../components/PlotPanel.svelte';
    import Segmented from '../components/ui/Segmented.svelte';
    import { loadPref, savePref, thin, type Plotted } from '../plotdata';
    import { redrawTicker, stationRows, type StationRow } from '../stations';
    import { store } from '../store.svelte';

    type Window = 60 | 600 | 3600 | 0;
    let windowSeconds = $state<Window>(loadPref('rts-window-v2', 60));
    let mode = $state<'position' | 'polar'>(loadPref('rts-mode', 'position'));
    let hidden = $state<string[]>(loadPref('rts-hidden-stations', []));
    $effect(() => savePref('rts-window-v2', windowSeconds));
    $effect(() => savePref('rts-mode', mode));
    $effect(() => savePref('rts-hidden-stations', hidden));

    let rows = $derived(stationRows());
    let shown = $derived(rows.filter((r) => !hidden.includes(r.rts.id)));
    let anyLive = $derived(shown.some((r) => r.live));

    let tick = $state(0);
    $effect(() => redrawTicker(() => shown, () => tick++));

    function toggle(id: string) {
        hidden = hidden.includes(id) ? hidden.filter((h) => h !== id) : [...hidden, id];
    }

    function visible(r: StationRow): Plotted | null {
        const s = r.series;
        if (!s || s.cols.t.length === 0) return null;
        return thin(s.window(windowSeconds, r.live ? clock.server : s.lastT!));
    }

    // While something is live, the time window follows "now": idle stations only appear with "Whole job"
    let traces = $derived.by<Trace[]>(() => {
        void tick;
        void windowSeconds;
        return shown
            .filter((r) => !anyLive || r.live || windowSeconds === 0)
            .map((r) => ({ label: r.rts.name, color: r.color, station: { x: r.rts.station_x, y: r.rts.station_y }, live: r.live, data: visible(r) }));
    });

    function status(r: StationRow): string {
        if (r.live) return 'live';
        if (!r.job) return 'no data';
        return 'last measurement';
    }
</script>

<div class="space-y-3">
    <div class="panel flex flex-wrap items-center gap-x-4 gap-y-2 px-3 py-2">
        <span class="label">Stations</span>
        {#each rows as r (r.rts.id)}
            <label class="flex items-center gap-1.5 text-[13px]">
                <input type="checkbox" checked={!hidden.includes(r.rts.id)} onchange={() => toggle(r.rts.id)} />
                <span class="h-3 w-1 rounded-sm" style="background: {r.color}"></span>
                <span class="font-semibold">{r.rts.name}</span>
                <span class="text-xs text-muted">{status(r)}</span>
            </label>
        {/each}
        <span class="ml-auto flex flex-wrap items-center gap-2">
            <Segmented label="Values" bind:value={mode} options={[{ value: 'position', label: 'E/N/H' }, { value: 'polar', label: 'Hz/V/D' }]} />
            <Segmented
                label="Time span"
                bind:value={windowSeconds}
                options={[
                    { value: 60, label: '1 min' },
                    { value: 600, label: '10 min' },
                    { value: 3600, label: '1 h' },
                    { value: 0, label: 'Whole job' },
                ]}
            />
        </span>
    </div>

    {#if store.rts.length === 0}
        <p class="panel px-3 py-10 text-center text-muted">No total stations in this session.</p>
    {:else}
        <PlotPanel
            {traces}
            {mode}
            version={tick}
            follow={anyLive && windowSeconds > 0 ? windowSeconds : 0}
            title={anyLive ? 'Live' : 'Last measurements'}
            mapHeight={560}
            plotHeight={170}
        />
    {/if}
</div>
