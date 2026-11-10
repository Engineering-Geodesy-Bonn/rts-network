<script lang="ts">
    import type { Snippet } from 'svelte';
    import { clock } from '../clock.svelte';
    import { events } from '../events.svelte';
    import { href, type Page } from '../router.svelte';
    import { store } from '../store.svelte';
    import Icon from './ui/Icon.svelte';

    let { page, children }: { page: Page; children: Snippet } = $props();

    const NAV: { id: Page; label: string; icon: string }[] = [
        { id: 'measure', label: 'Measure', icon: 'activity' },
        { id: 'data', label: 'Data', icon: 'list' },
        { id: 'setup', label: 'Setup', icon: 'settings' },
    ];

    let sessionId = $derived(store.session?.id ?? null);
    let downSince = $state<number | null>(null);
    $effect(() => {
        if (events.state === 'open') downSince = null;
        else downSince ??= Date.now() / 1000;
    });
    let offlineFor = $derived(downSince === null ? 0 : clock.now - downSince);
</script>

<div class="flex min-h-dvh flex-col">
    <header class="sticky top-0 z-40 border-b border-line bg-surface pt-[env(safe-area-inset-top)]">
        <div class="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
            <a href="#/" class="flex min-w-0 items-center gap-2 font-semibold" title="Switch session">
                <Icon name="chevronLeft" size={18} class="text-faint" />
                <span class="truncate">{store.session?.name ?? ''}</span>
            </a>
            <nav class="hidden h-full items-stretch gap-1 md:flex">
                {#each NAV as item (item.id)}
                    <a
                        href={href(sessionId, item.id)}
                        class="flex items-center border-b-2 px-3 text-[15px] font-medium {page === item.id ? 'border-accent text-fg' : 'border-transparent text-muted hover:text-fg'}"
                        >{item.label}</a
                    >
                {/each}
            </nav>
            {#if offlineFor > 3}
                <span class="ml-auto flex items-center gap-1.5 text-sm font-medium text-bad"><Icon name="wifiOff" size={16} /> Offline</span>
            {/if}
        </div>
    </header>

    {#if offlineFor > 3}
        <div class="bg-bad-soft px-4 py-2.5 text-center text-sm text-bad">
            No connection to the server. The values below may be outdated. The stations keep measuring and upload their data when the connection is back.
        </div>
    {/if}

    <main class="mx-auto w-full max-w-6xl flex-1 px-4 py-6 pb-28 md:pb-10">
        {#if store.sessionError && !store.session}
            <div class="mx-auto mt-16 max-w-md text-center">
                <p class="text-lg font-semibold">This session cannot be loaded</p>
                <p class="mt-1 text-muted">{store.sessionError}</p>
                <a class="mt-4 inline-block text-accent" href="#/">Back to all sessions</a>
            </div>
        {:else if store.session}
            {@render children()}
        {:else}
            <div class="mt-24 flex justify-center"><span class="h-6 w-6 animate-spin rounded-full border-2 border-faint border-t-transparent"></span></div>
        {/if}
    </main>

    <nav class="fixed inset-x-0 bottom-0 z-40 grid grid-cols-3 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] md:hidden">
        {#each NAV as item (item.id)}
            <a href={href(sessionId, item.id)} class="flex flex-col items-center gap-0.5 py-2.5 text-xs font-medium {page === item.id ? 'text-accent' : 'text-muted'}">
                <Icon name={item.icon} size={22} />
                {item.label}
            </a>
        {/each}
    </nav>
</div>
