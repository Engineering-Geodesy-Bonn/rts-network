<script lang="ts">
    import { onDestroy } from "svelte";
    import { currentSession } from "./lib/stores/session";
    import SessionPage from "./lib/components/SessionPage.svelte";
    import MainPage from "./lib/components/MainPage.svelte";
    import type { SessionResponse } from "./lib/api/types";

    let session = $state<SessionResponse | null>(null);

    const unsub = currentSession.subscribe((s) => {
        session = s;
    });

    onDestroy(unsub);
</script>

{#if session}
    <MainPage />
{:else}
    <SessionPage />
{/if}
