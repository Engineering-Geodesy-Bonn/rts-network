<script lang="ts">
    import { onMount } from 'svelte';
    import Shell from './lib/components/Shell.svelte';
    import Overlays from './lib/components/ui/Overlays.svelte';
    import { events } from './lib/events.svelte';
    import DataPage from './lib/pages/DataPage.svelte';
    import JobPage from './lib/pages/JobPage.svelte';
    import MeasurePage from './lib/pages/MeasurePage.svelte';
    import PlotPage from './lib/pages/PlotPage.svelte';
    import SensorsPage from './lib/pages/SensorsPage.svelte';
    import SessionsPage from './lib/pages/SessionsPage.svelte';
    import SettingsPage from './lib/pages/SettingsPage.svelte';
    import SetupPage from './lib/pages/SetupPage.svelte';
    import { router } from './lib/router.svelte';
    import { store } from './lib/store.svelte';
    import './lib/theme.svelte';

    onMount(() => events.start());

    let route = $derived(router.route);

    $effect(() => {
        if (route.name === 'session' && route.sessionId) void store.open(route.sessionId);
        else if (route.name === 'sessions') store.close();
    });
</script>

{#if route.name === 'sessions'}
    <SessionsPage />
{:else if route.name === 'settings'}
    <SettingsPage />
{:else}
    <Shell page={route.page}>
        {#if route.page === 'measure'}
            <MeasurePage />
        {:else if route.page === 'plot'}
            <PlotPage />
        {:else if route.page === 'sensors'}
            <SensorsPage />
        {:else if route.page === 'data'}
            {#if route.id}
                {#key route.id}<JobPage jobId={route.id} />{/key}
            {:else}
                <DataPage />
            {/if}
        {:else}
            <SetupPage />
        {/if}
    </Shell>
{/if}

<Overlays />
