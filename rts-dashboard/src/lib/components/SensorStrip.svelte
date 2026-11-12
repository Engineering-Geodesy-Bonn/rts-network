<!-- Compact state of the external sensors and the synchronization for the Measure page. -->
<script lang="ts">
    import { href } from '../router.svelte';
    import { sensorColor, sensorStore } from '../sensors.svelte';
    import { store } from '../store.svelte';

    $effect(() => sensorStore.use());

    let sync = $derived(sensorStore.sync);
    let show = $derived(sensorStore.sensors.length > 0 || (sync && sync.phase !== 'off'));
    const PHASE = { off: '', waiting: 'waiting for data', calibrating: 'calibrating', matching: 'matching positions', estimating: 'estimating' };
    const ms = (s: number) => `${s < 0 ? '−' : ''}${Math.abs(s * 1000).toFixed(2)}`;
</script>

{#if show}
    <a href={href(store.session?.id ?? null, 'sensors')} class="panel flex flex-wrap items-center gap-x-5 gap-y-1.5 px-3 py-2 text-[13px] hover:border-line-strong">
        <span class="label">Sensors</span>
        {#each sensorStore.sensors as s, i (s.id)}
            <span class="flex items-center gap-1.5">
                <span class="h-2.5 w-2.5 rounded-full" style="background: {sensorColor(i)}"></span>
                <span class="font-semibold">{s.name}</span>
                {#if s.online}<span class="num text-muted">{s.rate_hz?.toFixed(1)} Hz</span>{:else}<span class="text-bad">offline</span>{/if}
                {#if s.logging_active}<span class="rounded-[3px] bg-bad-soft px-1 text-[10px] font-bold text-bad">REC</span>{/if}
            </span>
        {/each}
        {#if sync && sync.phase !== 'off'}
            <span class="ml-auto flex items-center gap-1.5">
                <span class="text-muted">Sync</span>
                {#if sync.phase === 'estimating'}
                    <span class="num font-semibold">Δt {ms(sync.delta_t)} ± {ms(sync.sigma_delta_t)} ms</span>
                    {#if sync.converged}<span class="text-good">✓</span>{/if}
                {:else}
                    <span class={sync.phase === 'waiting' ? 'text-warn' : 'text-muted'}>{PHASE[sync.phase]}</span>
                {/if}
            </span>
        {/if}
    </a>
{/if}
