<script lang="ts">
    import { onMount } from 'svelte';
    import { api } from '../api';
    import Button from '../components/ui/Button.svelte';
    import Field from '../components/ui/Field.svelte';
    import Modal from '../components/ui/Modal.svelte';
    import Panel from '../components/ui/Panel.svelte';
    import { events } from '../events.svelte';
    import { fmtCount } from '../format';
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

    const pad = (v: number) => String(v).padStart(2, '0');
    function stamp(epoch: number | null): string {
        if (epoch == null) return '–';
        const d = new Date(epoch * 1000);
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    }

    let visible = $derived(sessions.filter((s) => showArchived || !s.archived));
    let archived = $derived(sessions.filter((s) => s.archived).length);
</script>

<header class="bg-bar text-bar-fg pt-[env(safe-area-inset-top)]">
    <div class="mx-auto flex h-11 max-w-[1500px] items-center gap-3 px-3 sm:px-4">
        <span class="label !text-bar-muted">RTS Network</span>
        <span class="text-bar-muted">/</span>
        <span class="text-[13px] font-semibold">Sessions</span>
        <a class="ml-auto text-xs font-semibold tracking-wider text-bar-muted uppercase hover:text-bar-fg" href="#/settings">Settings</a>
    </div>
</header>

<main class="mx-auto max-w-[1500px] px-3 py-4 sm:px-4">
    <Panel title="Sessions" flush>
        {#snippet actions()}
            {#if archived > 0}
                <label class="flex items-center gap-1.5 text-xs text-muted"><input type="checkbox" bind:checked={showArchived} /> Show archived ({archived})</label>
            {/if}
            <Button variant="primary" icon="plus" onclick={() => ((name = ''), (creating = true))}>New session</Button>
        {/snippet}
        {#if loading}
            <div class="flex justify-center py-12"><span class="h-5 w-5 animate-spin rounded-full border-2 border-faint border-t-transparent"></span></div>
        {:else if error}
            <div class="p-4">
                <p class="font-semibold text-bad">The server cannot be reached</p>
                <p class="mt-1 text-muted">{error}</p>
                <p class="mt-3">Check the network connection, or <a class="text-accent underline" href="#/settings">change the server address</a>.</p>
            </div>
        {:else if visible.length === 0}
            <p class="px-3 py-10 text-center text-muted">No sessions yet. A session holds the total stations and measurements of one campaign.</p>
        {:else}
            <div class="overflow-x-auto">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Created</th>
                            <th>Last activity</th>
                            <th class="r">Stations</th>
                            <th class="r">Jobs</th>
                            <th class="r">Points</th>
                            <th>Notes</th>
                        </tr>
                    </thead>
                    <tbody>
                        {#each visible as s (s.id)}
                            <tr class="link" onclick={() => navigate(href(s.id, 'measure'))}>
                                <td><a href={href(s.id, 'measure')} class="font-semibold">{s.name}</a>{#if s.archived}<span class="ml-2 text-xs text-muted">archived</span>{/if}</td>
                                <td class="num">{stamp(s.created_at)}</td>
                                <td class="num">{stamp(s.last_activity)}</td>
                                <td class="r num">{s.rts_count}</td>
                                <td class="r num">{fmtCount(s.job_count)}</td>
                                <td class="r num">{fmtCount(s.measurement_count)}</td>
                                <td class="max-w-80 truncate text-muted">{s.notes}</td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            </div>
        {/if}
    </Panel>
</main>

<Modal bind:open={creating} title="New session">
    <Field label="Name"><!-- svelte-ignore a11y_autofocus --><input bind:value={name} maxlength="200" placeholder="e.g. Bridge test 2026-11-10" autofocus onkeydown={(e) => e.key === 'Enter' && name.trim() && create()} /></Field>
    {#snippet footer()}
        <Button onclick={() => (creating = false)}>Cancel</Button>
        <Button variant="primary" {busy} disabled={!name.trim()} onclick={create}>Create</Button>
    {/snippet}
</Modal>
