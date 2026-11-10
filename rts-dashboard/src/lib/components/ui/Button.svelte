<script lang="ts">
    import type { Snippet } from 'svelte';
    import Icon from './Icon.svelte';

    let {
        variant = 'default',
        size = 'md',
        icon = '',
        busy = false,
        disabled = false,
        title = '',
        href = '',
        class: className = '',
        onclick,
        children,
    }: {
        variant?: 'default' | 'primary' | 'start' | 'stop' | 'quiet' | 'danger';
        size?: 'sm' | 'md' | 'lg';
        icon?: string;
        busy?: boolean;
        disabled?: boolean;
        title?: string;
        href?: string;
        class?: string;
        onclick?: (e: MouseEvent) => void;
        children?: Snippet;
    } = $props();

    const variants = {
        default: 'bg-surface text-fg border-line-strong hover:bg-surface-2',
        primary: 'bg-accent text-accent-fg border-transparent hover:brightness-110',
        start: 'bg-good text-surface border-transparent hover:brightness-110',
        stop: 'bg-surface text-bad border-bad/60 hover:bg-bad-soft',
        quiet: 'bg-transparent text-muted border-transparent hover:bg-surface-2 hover:text-fg',
        danger: 'bg-transparent text-bad border-transparent hover:bg-bad-soft',
    };
    const sizes = { sm: 'h-7 px-2.5 text-xs gap-1', md: 'h-8 px-3 text-[13px] gap-1.5', lg: 'h-10 px-4 text-sm gap-2' };
    let classes = $derived(
        `inline-flex items-center justify-center rounded-[5px] border font-medium whitespace-nowrap transition select-none disabled:opacity-45 disabled:pointer-events-none ${variants[variant]} ${sizes[size]} ${className}`,
    );
</script>

{#if href}
    <a {href} class={classes} {title}>
        {#if icon}<Icon name={icon} size={14} />{/if}
        {@render children?.()}
    </a>
{:else}
    <button type="button" class={classes} disabled={disabled || busy} {title} aria-label={children ? undefined : title} {onclick}>
        {#if busy}
            <span class="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
        {:else if icon}
            <Icon name={icon} size={14} />
        {/if}
        {@render children?.()}
    </button>
{/if}
