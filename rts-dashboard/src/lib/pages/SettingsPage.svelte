<script lang="ts">
    import { onMount } from 'svelte';
    import { api, apiBase, setApiBase } from '../api';
    import Button from '../components/ui/Button.svelte';
    import Field from '../components/ui/Field.svelte';
    import Icon from '../components/ui/Icon.svelte';
    import Segmented from '../components/ui/Segmented.svelte';
    import { events } from '../events.svelte';
    import { backFromSettings } from '../router.svelte';
    import { fmtBytes, fmtCount, fmtDateTime } from '../format';
    import { theme, type Theme } from '../theme.svelte';
    import { toast } from '../toast.svelte';
    import type { ServerInfo } from '../types';

    let url = $state(apiBase());
    let testing = $state(false);
    let info = $state<ServerInfo | null>(null);
    let themeValue = $state<Theme>(theme.theme);
    $effect(() => theme.set(themeValue));

    onMount(() => {
        api.info().then((i) => (info = i)).catch(() => {});
    });

    async function connect() {
        testing = true;
        const previous = apiBase();
        setApiBase(url.trim() || null);
        try {
            await api.ping();
            events.restart();
            info = await api.info();
            toast.ok('Connected');
        } catch (e) {
            setApiBase(previous);
            toast.error(`No server at ${url}`);
        } finally {
            testing = false;
        }
    }
</script>

<main class="mx-auto max-w-2xl px-4 pt-[max(2rem,env(safe-area-inset-top))] pb-16">
    <a class="mb-6 inline-flex items-center gap-1 text-muted hover:text-fg" href={backFromSettings()}><Icon name="chevronLeft" size={18} /> Back</a>
    <h1 class="mb-5 text-[17px] font-semibold">Settings</h1>

    <div class="panel space-y-6 p-4">
        <section>
            <h2 class="label mb-2">Appearance</h2>
            <Segmented label="Theme" bind:value={themeValue} options={[{ value: 'system', label: 'Automatic' }, { value: 'light', label: 'Light' }, { value: 'dark', label: 'Dark' }]} />
            <p class="mt-1.5 text-xs text-muted">Light is easiest to read in sunlight.</p>
        </section>

        <section>
            <h2 class="label mb-2">Server</h2>
            <div class="flex items-end gap-2">
                <Field label="Address" hint="Keep /api unless the dashboard runs on another machine than the server." class="flex-1"><input bind:value={url} placeholder="/api" /></Field>
            </div>
            <div class="mt-3"><Button variant="primary" busy={testing} onclick={connect}>Connect</Button></div>
        </section>

        {#if info}
            <section class="text-sm text-muted">
                <p>Server version {info.version} · database {fmtBytes(info.db_size)}</p>
                {#if info.legacy_import?.counts}
                    <p class="mt-1">
                        {info.legacy_import.ok ? 'Imported' : 'Partly imported'} from version 1{info.legacy_import.started_at ? ` on ${fmtDateTime(info.legacy_import.started_at)}` : ''}:
                        {fmtCount(info.legacy_import.counts.sessions ?? 0)} sessions, {fmtCount(info.legacy_import.counts.measurements ?? 0)} measurements.
                    </p>
                    {#each info.legacy_import.problems ?? [] as p (p)}<p class="text-bad">{p}</p>{/each}
                {/if}
                <p class="mt-1"><a class="hover:text-fg" href="{apiBase()}/docs" target="_blank" rel="noreferrer">API documentation</a></p>
            </section>
        {/if}
    </div>
</main>
