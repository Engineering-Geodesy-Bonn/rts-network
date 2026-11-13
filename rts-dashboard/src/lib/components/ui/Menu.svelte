<!--
    Dropdown menu. The list is positioned relative to the window (position: fixed), so that
    scroll containers such as tables never clip it. It opens upwards when there is no room below.
-->
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

    let { items, label = 'More actions', note = '' }: { items: MenuItem[]; label?: string; note?: string } = $props();
    let open = $state(false);
    let button: HTMLButtonElement;
    let list = $state<HTMLDivElement>();
    let position = $state('');

    const WIDTH = 290;
    const GAP = 4;

    function place() {
        const rect = button.getBoundingClientRect();
        const height = list?.offsetHeight ?? items.length * 36 + 8;
        const left = Math.max(8, Math.min(rect.right - WIDTH, window.innerWidth - WIDTH - 8));
        const below = rect.bottom + GAP + height <= window.innerHeight - 8;
        const top = below ? rect.bottom + GAP : Math.max(8, rect.top - GAP - height);
        position = `top: ${top}px; left: ${left}px; width: ${WIDTH}px;`;
    }

    function toggle() {
        open = !open;
        if (open) {
            place();
            requestAnimationFrame(place); // again with the measured height of the list
        }
    }

    function close() {
        open = false;
    }

    function onwindowclick(e: MouseEvent) {
        const target = e.target as Node;
        if (open && !button.contains(target) && !list?.contains(target)) close();
    }
</script>

<svelte:window
    onclick={onwindowclick}
    onkeydown={(e) => e.key === 'Escape' && close()}
    onresize={close}
    onscrollcapture={(e) => open && !list?.contains(e.target as Node) && close()}
/>

<button
    bind:this={button}
    class="inline-flex h-10 w-10 shrink-0 items-center justify-center md:h-8 md:w-8 rounded-[5px] border border-line-strong text-muted hover:bg-surface-2 hover:text-fg"
    aria-label={label}
    title={label}
    aria-haspopup="menu"
    aria-expanded={open}
    onclick={toggle}
>
    <Icon name="more" size={16} />
</button>
{#if open}
    <div bind:this={list} class="fixed z-[70] overflow-hidden rounded-[6px] border border-line-strong bg-surface py-1 shadow-lg" style={position} role="menu">
        {#if note}<p class="border-b border-line px-3 pt-1 pb-2 text-xs text-muted">{note}</p>{/if}
        {#each items as item (item.label)}
            <button
                role="menuitem"
                class="flex w-full items-center px-3 py-3 text-left text-sm md:py-2 md:text-[13px] hover:bg-surface-2 disabled:opacity-40 {item.danger ? 'text-bad' : ''}"
                disabled={item.disabled}
                onclick={() => {
                    close();
                    item.onclick();
                }}
            >
                {item.label}
            </button>
        {/each}
    </div>
{/if}
