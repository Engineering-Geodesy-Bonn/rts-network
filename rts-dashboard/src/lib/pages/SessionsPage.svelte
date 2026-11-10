<script lang="ts">
    import { onMount } from 'svelte';
    import { api } from '../api';
    import Button from '../components/ui/Button.svelte';
    import Field from '../components/ui/Field.svelte';
    import Modal from '../components/ui/Modal.svelte';
    import { events } from '../events.svelte';
    import { fmtCount, fmtDateTime } from '../format';
    import { href, navigate } from '../router.svelte';
    import { toast } from '../toast.svelte';
    import type { Session } from '../types';

    let sessions = $state<Session[]>([]);
    let loading = $state(true);
    let error = $state('');
    let showArchived = $state(false);
    let creating = $state(false);
    let name = $state('');
    let busy = $state(false);

    async function load() {
        try {
            sessions = await api.sessions();
            error = '';
        } catch (e) {
            error = (e as Error).message;
        } finally {
            loading = false;
        }
    }

    onMount(() => {
        void load();
        const off = events.on((e) => e.type === 'changed' && e.entity === 'session' && void load());
        const offOpen = events.onOpen(() => void load());
        return () => (off(), offOpen());
    });

    async function create() {
        busy = true;
        try {
            const session = await api.createSession(name.trim());
            navigate(href(session.id, 'setup'));
        } catch (e) {
            toast.error((e as Error).message);
        } finally {
            busy = false;
        }
    }

    let visible = $derived(sessions.filter((s) => showArchived || !s.archived));
    let archived = $derived(sessions.length - sessions.filter((s) => !s.archived).length);
</script>

<main class="mx-auto max-w-3xl px-4 pt-[max(2.5rem,env(safe-area-inset-top))] pb-16">
    <div class="mb-8 flex items-center gap-3">
        <img src="/favicon.png" alt="" class="h-9 w-9 rounded-lg" />
        <h1 class="mr-auto text-2xl font-semibold">RTS Network</h1>
        <Button variant="primary" icon="plus" onclick={() => ((name = ''), (creating = true))}>New session</Button>
    </div>

    {#if loading}
        <div class="mt-16 flex justify-center"><span class="h-6 w-6 animate-spin rounded-full border-2 border-faint border-t-transparent"></span></div>
    {:else if error}
        <div class="card p-6">
            <p class="font-semibold text-bad">The server cannot be reached</p>
            <p class="mt-1 text-muted">{error}</p>
            <p class="mt-4">Check the Wi-Fi connection, or <a class="text-accent underline" href="#/settings">change the server address</a>.</p>
        </div>
    {:else if visible.length === 0}
        <div class="card p-10 text-center">
            <p class="text-lg font-semibold">No sessions yet</p>
            <p class="mt-1 text-muted">A session holds the total stations and measurements of one campaign.</p>
        </div>
    {:else}
        <ul class="card">
            {#each visible as s (s.id)}
                <li class="border-b border-line last:border-b-0">
                    <a href={href(s.id, 'measure')} class="flex flex-wrap items-center gap-x-6 gap-y-1 px-5 py-4 hover:bg-surface-2">
                        <span class="min-w-48 flex-1">
                            <span class="block text-[17px] font-semibold">{s.name}{#if s.archived}<span class="ml-2 text-sm font-normal text-muted">archived</span>{/if}</span>
                            <span class="block text-sm text-muted">{fmtDateTime(s.last_activity ?? s.created_at)}</span>
                        </span>
                        <span class="num text-sm text-muted">{s.rts_count} station{s.rts_count === 1 ? '' : 's'} · {fmtCount(s.measurement_count)} points</span>
                    </a>
                </li>
            {/each}
        </ul>
    {/if}

    <div class="mt-6 flex justify-between text-sm">
        {#if archived > 0}
            <button class="text-muted hover:text-fg" onclick={() => (showArchived = !showArchived)}>{showArchived ? 'Hide' : 'Show'} archived ({archived})</button>
        {:else}<span></span>{/if}
        <a class="text-muted hover:text-fg" href="#/settings">Settings</a>
    </div>
</main>

<Modal bind:open={creating} title="New session">
    <Field label="Name"><!-- svelte-ignore a11y_autofocus --><input bind:value={name} maxlength="200" placeholder="e.g. Bridge test, 10 Nov" autofocus onkeydown={(e) => e.key === 'Enter' && name.trim() && create()} /></Field>
    {#snippet footer()}
        <Button onclick={() => (creating = false)}>Cancel</Button>
        <Button variant="primary" {busy} disabled={!name.trim()} onclick={create}>Create</Button>
    {/snippet}
</Modal>
