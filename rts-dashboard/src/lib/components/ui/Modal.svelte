<script lang="ts">
    import type { Snippet } from 'svelte';
    import Icon from './Icon.svelte';

    let {
        open = $bindable(false),
        title,
        wide = false,
        children,
        footer,
        onclose,
    }: {
        open?: boolean;
        title: string;
        wide?: boolean;
        children: Snippet;
        footer?: Snippet;
        onclose?: () => void;
    } = $props();

    function close() {
        open = false;
        onclose?.();
    }

    function onkeydown(e: KeyboardEvent) {
        if (open && e.key === 'Escape') close();
    }
</script>

<svelte:window {onkeydown} />

{#if open}
    <div class="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4" role="presentation">
        <button class="absolute inset-0 bg-black/50 backdrop-blur-[1px]" aria-label="Close" onclick={close}></button>
        <div
            class="relative flex max-h-[92dvh] w-full flex-col rounded-t-2xl bg-surface shadow-2xl sm:rounded-2xl {wide ? 'sm:max-w-3xl' : 'sm:max-w-lg'}"
            role="dialog"
            aria-modal="true"
            aria-label={title}
        >
            <header class="flex items-center justify-between gap-3 px-6 pt-5 pb-2">
                <h2 class="text-lg font-semibold">{title}</h2>
                <button class="rounded-md p-1 text-muted hover:bg-surface-2 hover:text-fg" aria-label="Close" onclick={close}>
                    <Icon name="x" />
                </button>
            </header>
            <div class="overflow-y-auto px-6 py-3">
                {@render children()}
            </div>
            {#if footer}
                <footer class="flex flex-wrap justify-end gap-2 px-6 pt-3 pb-[max(1.25rem,env(safe-area-inset-bottom))]">
                    {@render footer()}
                </footer>
            {/if}
        </div>
    </div>
{/if}
