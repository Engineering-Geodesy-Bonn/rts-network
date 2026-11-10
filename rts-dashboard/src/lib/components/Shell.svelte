<script lang="ts">
    import type { Snippet } from 'svelte';
    import { clock } from '../clock.svelte';
    import { events } from '../events.svelte';
    import { STATUS_LABEL } from '../format';
    import { href, type Page } from '../router.svelte';
    import { store } from '../store.svelte';
    import ConnectionIndicator from './ConnectionIndicator.svelte';
    import Badge from './ui/Badge.svelte';
    import Icon from './ui/Icon.svelte';

    let { page, children }: { page: Page; children: Snippet } = $props();

    const NAV: { id: Page; label: string; icon: string }[] = [
        { id: 'measure', label: 'Measure', icon: 'activity' },
        { id: 'stations', label: 'Stations', icon: 'crosshair' },
        { id: 'jobs', label: 'History', icon: 'list' },
        { id: 'health', label: 'Health', icon: 'heart' },
        { id: 'advanced', label: 'More', icon: 'sliders' },
    ];

    let sessionId = $derived(store.session?.id ?? null);
    let boardAge = $derived(store.boardReceivedAt ? clock.now - store.boardReceivedAt / 1000 : null);
    let boardStale = $derived(boardAge === null || boardAge > 8);
    let overall = $derived(store.board && !boardStale ? store.board.overall : 'unknown');
    let disconnectedFor = $state(0);
    let downSince: number | null = null;

    $effect(() => {
        if (events.state === 'open') {
            downSince = null;
            disconnectedFor = 0;
        } else {
            downSince ??= clock.now;
            disconnectedFor = clock.now - downSince;
        }
    });
</script>

<div class="flex min-h-dvh flex-col">
    <header class="sticky top-0 z-40 border-b border-line bg-surface/95 backdrop-blur pt-[env(safe-area-inset-top)]">
        <div class="mx-auto flex h-14 max-w-[1600px] items-center gap-3 px-4">
            <a href="#/" class="flex min-w-0 items-center gap-2.5" title="All sessions">
                <img src="/favicon.png" alt="" class="h-7 w-7 rounded" />
                <span class="hidden text-sm text-muted sm:inline">RTS Network</span>
                <Icon name="chevronRight" size={14} class="hidden text-muted sm:inline" />
                <span class="truncate font-semibold">{store.session?.name ?? 'Loading…'}</span>
            </a>
            <nav class="ml-4 hidden items-center gap-1 md:flex">
                {#each NAV as item (item.id)}
                    <a
                        href={href(sessionId, item.id)}
                        class="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition {page === item.id
                            ? 'bg-surface-2 text-fg'
                            : 'text-muted hover:bg-surface-2 hover:text-fg'}"
                    >
                        <Icon name={item.icon} size={16} />
                        {item.label}
                    </a>
                {/each}
            </nav>
            <div class="ml-auto flex items-center gap-3">
                <a href={href(sessionId, 'health')} title="Network health">
                    <Badge tone={overall} pulse={overall === 'fail'}>
                        {store.board && !boardStale ? STATUS_LABEL[overall] : 'Health unknown'}
                    </Badge>
                </a>
                <ConnectionIndicator />
                <a href="#/settings" class="rounded-md p-1.5 text-muted hover:bg-surface-2 hover:text-fg" title="Settings">
                    <Icon name="settings" />
                </a>
            </div>
        </div>
        {#if events.state !== 'open' && disconnectedFor > 4}
            <div class="border-t border-fail/30 bg-fail-bg px-4 py-2 text-center text-sm font-medium text-fail">
                No connection to the server for {Math.round(disconnectedFor)} s. Values shown may be outdated. Measurements continue on the workers and are uploaded when the connection is back.
            </div>
        {/if}
    </header>

    <main class="mx-auto w-full max-w-[1600px] flex-1 px-3 py-4 pb-24 sm:px-4 md:pb-8">
        {#if store.sessionError && !store.session}
            <div class="mx-auto mt-16 max-w-md text-center">
                <p class="font-semibold">Cannot load the session</p>
                <p class="mt-1 text-sm text-muted">{store.sessionError}</p>
                <a class="mt-4 inline-block text-sm text-accent" href="#/">Back to all sessions</a>
            </div>
        {:else if store.session}
            {@render children()}
        {:else}
            <div class="mt-24 flex justify-center"><span class="h-6 w-6 animate-spin rounded-full border-2 border-muted border-t-transparent"></span></div>
        {/if}
    </main>

    <!-- bottom navigation on phones -->
    <nav class="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] md:hidden">
        {#each NAV as item (item.id)}
            <a
                href={href(sessionId, item.id)}
                class="flex flex-col items-center gap-0.5 py-2 text-[11px] font-medium {page === item.id ? 'text-accent' : 'text-muted'}"
            >
                <Icon name={item.icon} size={20} />
                {item.label}
            </a>
        {/each}
    </nav>
</div>
