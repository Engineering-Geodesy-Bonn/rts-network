<script lang="ts">
    import { onMount } from 'svelte';
    import { api } from '../api';
    import ConnectionIndicator from '../components/ConnectionIndicator.svelte';
    import Button from '../components/ui/Button.svelte';
    import Field from '../components/ui/Field.svelte';
    import Icon from '../components/ui/Icon.svelte';
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
    let notes = $state('');
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
        const off = events.on((e) => {
            if (e.type === 'changed' && e.entity === 'session') void load();
        });
        const offOpen = events.onOpen(() => void load());
        return () => {
            off();
            offOpen();
        };
    });

    async function create(e: SubmitEvent) {
        e.preventDefault();
        busy = true;
        try {
            const session = await api.createSession(name.trim(), notes.trim());
            creating = false;
            navigate(href(session.id, 'stations'));
        } catch (err) {
            toast.error((err as Error).message);
        } finally {
            busy = false;
        }
    }

    let visible = $derived(sessions.filter((s) => showArchived || !s.archived));
    let archivedCount = $derived(sessions.filter((s) => s.archived).length);
</script>

<div class="min-h-dvh">
    <header class="border-b border-line bg-surface pt-[env(safe-area-inset-top)]">
        <div class="mx-auto flex h-14 max-w-5xl items-center gap-3 px-4">
            <img src="/favicon.png" alt="" class="h-7 w-7 rounded" />
            <span class="font-semibold">RTS Network</span>
            <div class="ml-auto flex items-center gap-3">
                <ConnectionIndicator />
                <a href="#/settings" class="rounded-md p-1.5 text-muted hover:bg-surface-2 hover:text-fg" title="Settings"><Icon name="settings" /></a>
            </div>
        </div>
    </header>

    <main class="mx-auto max-w-5xl px-4 py-8">
        <div class="mb-6 flex flex-wrap items-end justify-between gap-3">
            <div>
                <h1 class="text-2xl font-bold">Sessions</h1>
                <p class="mt-1 text-sm text-muted">A session groups the total stations of one measurement campaign and all their data.</p>
            </div>
            <Button variant="primary" icon="plus" onclick={() => ((name = ''), (notes = ''), (creating = true))}>New session</Button>
        </div>

        {#if loading}
            <div class="mt-16 flex justify-center"><span class="h-6 w-6 animate-spin rounded-full border-2 border-muted border-t-transparent"></span></div>
        {:else if error}
            <div class="rounded-xl border border-fail/40 bg-fail-bg p-5 text-sm text-fail">
                <p class="font-semibold">Cannot reach the API server</p>
                <p class="mt-1">{error}</p>
                <p class="mt-3 text-fg">Check the network connection or the <a class="text-accent underline" href="#/settings">server address</a>.</p>
            </div>
        {:else if visible.length === 0}
            <div class="rounded-2xl border border-dashed border-line p-10 text-center">
                <Icon name="folder" size={32} class="mx-auto text-muted" />
                <p class="mt-3 font-semibold">No sessions yet</p>
                <p class="mt-1 text-sm text-muted">Create a session, add your total stations and start measuring.</p>
            </div>
        {:else}
            <ul class="grid gap-3 sm:grid-cols-2">
                {#each visible as s (s.id)}
                    <li>
                        <a
                            href={href(s.id, 'measure')}
                            class="block rounded-xl border border-line bg-surface p-4 shadow-sm transition hover:border-accent/60 hover:shadow"
                        >
                            <div class="flex items-start justify-between gap-2">
                                <h2 class="truncate text-base font-semibold">{s.name}</h2>
                                {#if s.archived}<span class="rounded bg-surface-2 px-1.5 py-0.5 text-xs text-muted">Archived</span>{/if}
                            </div>
                            {#if s.notes}<p class="mt-1 line-clamp-2 text-sm text-muted">{s.notes}</p>{/if}
                            <dl class="mt-3 grid grid-cols-3 gap-2 text-sm">
                                <div><dt class="text-xs text-muted">Stations</dt><dd class="font-semibold tabular">{s.rts_count}</dd></div>
                                <div><dt class="text-xs text-muted">Jobs</dt><dd class="font-semibold tabular">{fmtCount(s.job_count)}</dd></div>
                                <div><dt class="text-xs text-muted">Measurements</dt><dd class="font-semibold tabular">{fmtCount(s.measurement_count)}</dd></div>
                            </dl>
                            <p class="mt-3 text-xs text-muted">
                                Created {fmtDateTime(s.created_at)}{#if s.last_activity} · last activity {fmtDateTime(s.last_activity)}{/if}
                            </p>
                        </a>
                    </li>
                {/each}
            </ul>
        {/if}
        {#if archivedCount > 0}
            <button class="mt-4 text-sm text-muted hover:text-fg" onclick={() => (showArchived = !showArchived)}>
                {showArchived ? 'Hide' : 'Show'} {archivedCount} archived session{archivedCount === 1 ? '' : 's'}
            </button>
        {/if}
    </main>
</div>

<Modal bind:open={creating} title="New session">
    <form id="create-session" class="space-y-4" onsubmit={create}>
        <Field label="Name">
            <!-- svelte-ignore a11y_autofocus -->
            <input bind:value={name} required maxlength="200" placeholder="e.g. Bridge monitoring 2026-11" autofocus />
        </Field>
        <Field label="Notes" hint="Optional: site, setup, people, weather …">
            <textarea bind:value={notes} rows="3"></textarea>
        </Field>
    </form>
    {#snippet footer()}
        <Button onclick={() => (creating = false)}>Cancel</Button>
        <Button variant="primary" busy={busy} disabled={!name.trim()} onclick={() => (document.getElementById('create-session') as HTMLFormElement)?.requestSubmit()}>Create</Button>
    {/snippet}
</Modal>
