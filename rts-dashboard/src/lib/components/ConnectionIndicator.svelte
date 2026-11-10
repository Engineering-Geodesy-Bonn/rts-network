<script lang="ts">
    import { clock } from '../clock.svelte';
    import { events } from '../events.svelte';
    import Icon from './ui/Icon.svelte';

    let { compact = false }: { compact?: boolean } = $props();
    let downSince = $state<number | null>(null);

    $effect(() => {
        if (events.state === 'open') downSince = null;
        else if (downSince === null) downSince = Date.now() / 1000;
    });

    let downFor = $derived(downSince === null ? 0 : clock.now - downSince);
    let tone = $derived(events.state === 'open' ? 'text-ok' : downFor > 10 ? 'text-fail' : 'text-warn');
    let label = $derived(events.state === 'open' ? 'Live' : downFor > 10 ? 'Offline' : 'Connecting…');
</script>

<span class="inline-flex items-center gap-1.5 text-xs font-semibold {tone}" title="Connection to the API server">
    <Icon name={events.state === 'open' ? 'wifi' : 'wifiOff'} size={16} />
    {#if !compact}{label}{/if}
</span>
