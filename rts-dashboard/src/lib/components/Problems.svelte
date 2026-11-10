<!-- Actionable problems of the session. Always present, so that "no problems" is a visible state. -->
<script lang="ts">
    import { clock } from '../clock.svelte';
    import { events } from '../events.svelte';
    import { store } from '../store.svelte';
    import Panel from './ui/Panel.svelte';
    import Tag from './ui/Tag.svelte';

    let stale = $derived(events.state !== 'open' || !store.healthReceivedAt || clock.now - store.healthReceivedAt / 1000 > 10);
    let problems = $derived(store.health?.problems ?? []);
</script>

<Panel title={stale ? 'Problems' : `Problems (${problems.length})`} flush>
    {#if stale}
        <p class="px-3 py-2.5 text-[13px] text-muted">Status unknown: waiting for the server.</p>
    {:else if problems.length === 0}
        <p class="flex items-center gap-2 px-3 py-2.5 text-[13px] text-muted"><Tag tone="good" text="OK" /> No problems detected.</p>
    {:else}
        <table class="data-table">
            <tbody>
                {#each problems as p, i (i)}
                    <tr>
                        <td class="w-20"><Tag tone={p.severity === 'error' ? 'bad' : 'warn'} text={p.severity === 'error' ? 'Error' : 'Warning'} /></td>
                        <td class="w-40 font-semibold">{p.subject}</td>
                        <td class="!whitespace-normal">{p.message}</td>
                    </tr>
                {/each}
            </tbody>
        </table>
    {/if}
</Panel>
