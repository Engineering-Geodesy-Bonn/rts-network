<script lang="ts">
    import { onMount } from 'svelte';
    import { api, apiBase, setApiBase } from '../api';
    import ConnectionIndicator from '../components/ConnectionIndicator.svelte';
    import Button from '../components/ui/Button.svelte';
    import Field from '../components/ui/Field.svelte';
    import Icon from '../components/ui/Icon.svelte';
    import { events } from '../events.svelte';
    import { fmtBytes, fmtCount, fmtDateTime, fmtDuration } from '../format';
    import { theme, type Theme } from '../theme.svelte';
    import { toast } from '../toast.svelte';
    import type { ServerInfo } from '../types';

    let url = $state(apiBase());
    let testing = $state(false);
    let info = $state<ServerInfo | null>(null);
    let infoError = $state('');

    async function loadInfo() {
        try {
            info = await api.info();
            infoError = '';
        } catch (e) {
            info = null;
            infoError = (e as Error).message;
        }
    }

    onMount(() => {
        void loadInfo();
    });

    async function save() {
        testing = true;
        const previous = apiBase();
        setApiBase(url.trim() || null);
        try {
            await api.ping();
            toast.ok('Connected to the server');
            events.restart();
            await loadInfo();
        } catch (e) {
            setApiBase(previous);
            toast.error(`Server not reachable at ${url}: ${(e as Error).message}`);
        } finally {
            testing = false;
        }
    }

    const THEMES: { value: Theme; label: string; icon: string }[] = [
        { value: 'system', label: 'Automatic', icon: 'refresh' },
        { value: 'light', label: 'Light (sunlight)', icon: 'sun' },
        { value: 'dark', label: 'Dark', icon: 'moon' },
    ];
</script>

<div class="min-h-dvh">
    <header class="border-b border-line bg-surface pt-[env(safe-area-inset-top)]">
        <div class="mx-auto flex h-14 max-w-3xl items-center gap-3 px-4">
            <button class="inline-flex items-center gap-1 text-sm text-muted hover:text-fg" onclick={() => history.back()}><Icon name="chevronLeft" size={16} /> Back</button>
            <span class="font-semibold">Settings</span>
            <span class="ml-auto"><ConnectionIndicator /></span>
        </div>
    </header>
    <main class="mx-auto max-w-3xl space-y-4 px-4 py-6">
        <section class="rounded-xl border border-line bg-surface p-4 shadow-sm">
            <h2 class="mb-3 font-semibold">Appearance</h2>
            <div class="inline-flex flex-wrap rounded-lg border border-line p-0.5">
                {#each THEMES as t (t.value)}
                    <button class="inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium {theme.theme === t.value ? 'bg-accent text-accent-fg' : 'text-muted hover:text-fg'}" onclick={() => theme.set(t.value)}>
                        <Icon name={t.icon} size={16} />{t.label}
                    </button>
                {/each}
            </div>
        </section>

        <section class="rounded-xl border border-line bg-surface p-4 shadow-sm">
            <h2 class="mb-1 font-semibold">API server</h2>
            <p class="mb-3 text-sm text-muted">Leave “/api” when the dashboard is served by the API host (default). Use a full URL such as http://192.168.0.101:8000 otherwise.</p>
            <div class="flex flex-col gap-2 sm:flex-row">
                <Field label="Address" class="flex-1"><input bind:value={url} placeholder="/api" /></Field>
                <div class="flex items-end gap-2">
                    <Button variant="primary" busy={testing} onclick={save}>Connect</Button>
                    <Button onclick={() => ((url = '/api'), save())}>Default</Button>
                </div>
            </div>
        </section>

        <section class="rounded-xl border border-line bg-surface p-4 shadow-sm">
            <h2 class="mb-3 font-semibold">Server</h2>
            {#if info}
                <dl class="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                    <div><dt class="text-xs text-muted">Version</dt><dd>{info.version}</dd></div>
                    <div><dt class="text-xs text-muted">Running for</dt><dd>{fmtDuration(info.server_time - info.started_at)}</dd></div>
                    <div><dt class="text-xs text-muted">Clock offset to this device</dt><dd>{(events.serverOffset * 1000).toFixed(0)} ms</dd></div>
                    <div><dt class="text-xs text-muted">Database</dt><dd>{fmtBytes(info.db_size)}</dd></div>
                    <div><dt class="text-xs text-muted">Measurements stored</dt><dd>{fmtCount(info.writer.inserted)} since start</dd></div>
                    <div><dt class="text-xs text-muted">Dashboards connected</dt><dd>{info.event_clients}</dd></div>
                </dl>
                <p class="mt-3 truncate text-xs text-muted">{info.db_path} · schema v{info.schema_version}</p>
                {#if info.legacy_import}
                    {@const li = info.legacy_import}
                    <div class="mt-4 rounded-lg p-3 text-sm {li.ok ? 'bg-ok-bg' : 'bg-warn-bg'}">
                        <p class="font-semibold">{li.ok ? 'Data of the previous version imported' : 'Import of the previous version had problems'}</p>
                        <p class="mt-1 text-muted">
                            {li.source}{li.started_at ? ` · ${fmtDateTime(li.started_at)}` : ''}
                            {#if li.counts} · {fmtCount(li.counts.sessions ?? 0)} sessions, {fmtCount(li.counts.jobs ?? 0)} jobs, {fmtCount(li.counts.measurements ?? 0)} measurements{/if}
                            {#if li.jobs_verified != null} · {li.jobs_verified} jobs verified{/if}
                        </p>
                        {#each li.problems ?? [] as p (p)}<p class="mt-1 text-xs text-fail">{p}</p>{/each}
                    </div>
                {/if}
            {:else if infoError}
                <p class="text-sm text-fail">{infoError}</p>
            {/if}
        </section>

        <p class="text-center text-xs text-muted"><a class="hover:text-fg" href="{apiBase()}/docs" target="_blank" rel="noreferrer">API documentation</a></p>
    </main>
</div>
