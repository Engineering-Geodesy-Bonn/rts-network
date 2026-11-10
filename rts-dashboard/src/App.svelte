<script lang="ts">
    import { onMount } from 'svelte';
    import Overlays from './lib/components/ui/Overlays.svelte';
    import Shell from './lib/components/Shell.svelte';
    import { events } from './lib/events.svelte';
    import AdvancedPage from './lib/pages/AdvancedPage.svelte';
    import HealthPage from './lib/pages/HealthPage.svelte';
    import JobDetailPage from './lib/pages/JobDetailPage.svelte';
    import JobsPage from './lib/pages/JobsPage.svelte';
    import MeasurePage from './lib/pages/MeasurePage.svelte';
    import SessionsPage from './lib/pages/SessionsPage.svelte';
    import SettingsPage from './lib/pages/SettingsPage.svelte';
    import StationsPage from './lib/pages/StationsPage.svelte';
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
        {:else if route.page === 'stations'}
            <StationsPage />
        {:else if route.page === 'jobs'}
            {#if route.id}
                {#key route.id}<JobDetailPage jobId={route.id} />{/key}
            {:else}
                <JobsPage />
            {/if}
        {:else if route.page === 'health'}
            <HealthPage />
        {:else if route.page === 'advanced'}
            <AdvancedPage />
        {/if}
    </Shell>
{/if}

<Overlays />
