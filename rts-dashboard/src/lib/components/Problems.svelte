<!-- The problems of the session, in plain words. Nothing is shown when everything is fine. -->
<script lang="ts">
    import { clock } from '../clock.svelte';
    import { events } from '../events.svelte';
    import { store } from '../store.svelte';

    let expanded = $state(false);
    let stale = $derived(!store.healthReceivedAt || clock.now - store.healthReceivedAt / 1000 > 10);
    let problems = $derived(store.health?.problems ?? []);
    let shown = $derived(expanded ? problems : problems.slice(0, 4));
</script>

{#if events.state === 'open' && !stale && problems.length > 0}
    <section class="card overflow-hidden" aria-label="Problems">
        <ul>
            {#each shown as p, i (i)}
                <li class="flex gap-3 border-b border-line px-5 py-3 last:border-b-0">
                    <span class="mt-2 h-2.5 w-2.5 shrink-0 rounded-full {p.severity === 'error' ? 'bg-bad' : 'bg-warn'}"></span>
                    <p><span class="font-semibold">{p.subject}</span> <span class="text-muted">·</span> {p.message}</p>
                </li>
            {/each}
        </ul>
        {#if problems.length > 4}
            <button class="w-full border-t border-line px-5 py-2 text-left text-sm text-muted hover:text-fg" onclick={() => (expanded = !expanded)}>
                {expanded ? 'Show less' : `Show ${problems.length - 4} more`}
            </button>
        {/if}
    </section>
{/if}
