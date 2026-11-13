<!-- Measure: problems and the station table with live values and actions. Plots are on the Plot tab. -->
<script lang="ts">
    import Problems from '../components/Problems.svelte';
    import SensorStrip from '../components/SensorStrip.svelte';
    import StationTable, { type StationEntry } from '../components/StationTable.svelte';
    import Button from '../components/ui/Button.svelte';
    import Segmented from '../components/ui/Segmented.svelte';
    import { confirm } from '../confirm.svelte';
    import { loadPref, savePref } from '../plotdata';
    import { href } from '../router.svelte';
    import { redrawTicker, stationRows } from '../stations';
    import { store } from '../store.svelte';

    let mode = $state<'position' | 'polar'>(loadPref('rts-mode', 'position'));
    $effect(() => savePref('rts-mode', mode));

    let rows = $derived(stationRows());
    let idle = $derived(rows.filter((r) => store.activeJobsOf(r.rts.id).length === 0));
    let measuring = $derived(rows.filter((r) => r.live));

    let tick = $state(0);
    $effect(() => redrawTicker(() => rows, () => tick++));

    let entries = $derived<StationEntry[]>(rows.map((r) => ({ rts: r.rts, color: r.color, series: r.series, lastJob: store.lastMeasuringJob[r.rts.id] })));

    async function startAll() {
        for (const r of idle) await store.startJob(r.rts.id, 'track_prism');
    }

    async function stopAll() {
        const ok = await confirm({
            title: `Stop all ${measuring.length} stations?`,
            message: 'The total stations stop measuring. Everything measured so far is kept.',
            confirm: 'Stop all',
            danger: true,
        });
        if (!ok) return;
        for (const r of measuring) {
            const job = store.runningJobOf(r.rts.id);
            if (job) await store.stopJob(job);
        }
    }
</script>

{#if store.rts.length === 0}
    <div class="panel mx-auto mt-10 max-w-md p-8 text-center">
        <p class="font-semibold">No total stations in this session</p>
        <p class="mt-1 text-muted">Add the total stations and their station setup first.</p>
        <Button variant="primary" class="mt-5" href={href(store.session?.id ?? null, 'setup')}>Go to setup</Button>
    </div>
{:else}
    <div class="space-y-3">
        <Problems />
        <SensorStrip />

        <div class="flex flex-wrap items-center gap-2 pt-1">
            <h1 class="label mr-auto !text-[12px] !text-fg">Stations</h1>
            <Segmented label="Values" bind:value={mode} options={[{ value: 'position', label: 'E/N/H' }, { value: 'polar', label: 'Hz/V/D' }]} />
            {#if idle.length > 1}<Button onclick={startAll}>Start all ({idle.length})</Button>{/if}
            {#if measuring.length > 1}<Button variant="stop" onclick={stopAll}>Stop all</Button>{/if}
        </div>
        <StationTable {entries} {mode} {tick} />
    </div>
{/if}
