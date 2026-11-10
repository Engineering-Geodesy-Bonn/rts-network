<script lang="ts" module>
    export interface MenuItem {
        label: string;
        icon?: string;
        danger?: boolean;
        disabled?: boolean;
        onclick: () => void;
    }
</script>

<script lang="ts">
    import Icon from './Icon.svelte';

    let { items, label = 'More actions' }: { items: MenuItem[]; label?: string } = $props();
    let open = $state(false);
    let root: HTMLDivElement;

    function onwindowclick(e: MouseEvent) {
        if (open && !root.contains(e.target as Node)) open = false;
    }
</script>

<svelte:window onclick={onwindowclick} onkeydown={(e) => e.key === 'Escape' && (open = false)} />

<div class="relative" bind:this={root}>
    <button
        class="inline-flex h-10 w-10 items-center justify-center rounded-lg text-muted hover:bg-surface-2 hover:text-fg"
        aria-label={label}
        title={label}
        aria-expanded={open}
        onclick={() => (open = !open)}
    >
        <Icon name="more" />
    </button>
    {#if open}
        <div class="absolute right-0 z-30 mt-1 min-w-52 overflow-hidden rounded-xl border border-line bg-surface py-1 shadow-xl" role="menu">
            {#each items as item (item.label)}
                <button
                    role="menuitem"
                    class="flex w-full items-center px-4 py-2.5 text-left text-[15px] hover:bg-surface-2 disabled:opacity-40 {item.danger ? 'text-bad' : ''}"
                    disabled={item.disabled}
                    onclick={() => {
                        open = false;
                        item.onclick();
                    }}
                >
                                        {item.label}
                </button>
            {/each}
        </div>
    {/if}
</div>
