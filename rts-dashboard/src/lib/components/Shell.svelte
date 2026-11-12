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
        { id: 'plot', label: 'Plot', icon: 'layers' },
        { id: 'data', label: 'Data', icon: 'list' },
        { id: 'sensors', label: 'Sensors', icon: 'satellite' },
        { id: 'setup', label: 'Setup', icon: 'settings' },
    ];

    let sessionId = $derived(store.session?.id ?? null);
    let downSince = $state<number | null>(null);
    $effect(() => {
        if (events.state === 'open') downSince = null;
        else downSince ??= Date.now() / 1000;
    });
    let offlineFor = $derived(downSince === null ? 0 : clock.now - downSince);
    let offline = $derived(offlineFor > 3);

    let measuring = $derived(store.health?.stations.filter((s) => s.state === 'measuring').length ?? 0);
    let errors = $derived(store.health?.problems.filter((p) => p.severity === 'error').length ?? 0);
    let warnings = $derived(store.health?.problems.filter((p) => p.severity === 'warning').length ?? 0);
    let time = $derived(new Date(clock.server * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }));
</script>

<div class="flex min-h-dvh flex-col">
    <header class="sticky top-0 z-40 bg-bar text-bar-fg pt-[env(safe-area-inset-top)]">
        <div class="mx-auto flex h-11 max-w-[1500px] items-center gap-4 px-3 sm:px-4">
            <a href="#/" class="flex min-w-0 items-center gap-2" title="All sessions">
                <span class="label hidden !text-bar-muted sm:inline">RTS Network</span>
                <span class="hidden text-bar-muted sm:inline">/</span>
                <span class="truncate text-[13px] font-semibold">{store.session?.name ?? ''}</span>
            </a>
            <nav class="hidden h-full items-stretch md:flex">
                {#each NAV as item (item.id)}
                    <a
                        href={href(sessionId, item.id)}
                        class="flex items-center border-b-2 px-3 text-xs font-semibold tracking-wider uppercase {page === item.id ? 'border-accent text-bar-fg' : 'border-transparent text-bar-muted hover:text-bar-fg'}"
                        >{item.label}</a
                    >
                {/each}
            </nav>
            <div class="ml-auto flex items-center gap-4 text-xs">
                {#if store.health && !offline}
                    <span class="hidden items-center gap-3 lg:flex">
                        <span class="text-bar-muted">MEASURING <span class="num text-bar-fg">{measuring}/{store.rts.length}</span></span>
                        <a href={href(sessionId, 'measure')} class="text-bar-muted">
                            PROBLEMS <span class="num {errors ? 'text-bad' : warnings ? 'text-warn' : 'text-bar-fg'}">{errors + warnings}</span>
                        </a>
                    </span>
                {/if}
                <span class="num text-bar-fg" title="Server time">{time}</span>
                <span class="flex items-center gap-1.5 font-semibold tracking-wider {offline ? 'text-bad' : events.state === 'open' ? 'text-good' : 'text-warn'}">
                    <span class="h-2 w-2 rounded-full bg-current"></span>{offline ? 'OFFLINE' : events.state === 'open' ? 'LIVE' : 'CONNECTING'}
                </span>
            </div>
        </div>
    </header>

    {#if offline}
        <div class="border-b border-bad/40 bg-bad-soft px-4 py-2 text-center text-[13px] text-bad">
            No connection to the server for <span class="num">{Math.round(offlineFor)}</span> s. Values may be outdated. The stations keep measuring and upload their data when the connection is back.
        </div>
    {/if}

    <main class="mx-auto w-full max-w-[1500px] flex-1 px-3 py-4 pb-24 sm:px-4 md:pb-8">
        {#if store.sessionError && !store.session}
            <div class="mx-auto mt-16 max-w-md text-center">
                <p class="font-semibold">This session cannot be loaded</p>
                <p class="mt-1 text-muted">{store.sessionError}</p>
                <a class="mt-4 inline-block text-accent" href="#/">Back to all sessions</a>
            </div>
        {:else if store.session}
            {@render children()}
        {:else}
            <div class="mt-24 flex justify-center"><span class="h-5 w-5 animate-spin rounded-full border-2 border-faint border-t-transparent"></span></div>
        {/if}
    </main>

    <nav class="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 bg-bar pb-[env(safe-area-inset-bottom)] md:hidden">
        {#each NAV as item (item.id)}
            <a href={href(sessionId, item.id)} class="flex flex-col items-center gap-0.5 py-2 text-[11px] font-semibold tracking-wider uppercase {page === item.id ? 'text-bar-fg' : 'text-bar-muted'}">
                <Icon name={item.icon} size={19} />
                {item.label}
            </a>
        {/each}
    </nav>
</div>
