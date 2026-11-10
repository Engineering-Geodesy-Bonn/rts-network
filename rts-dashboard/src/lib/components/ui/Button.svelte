<script lang="ts">
    import type { Snippet } from 'svelte';
    import Icon from './Icon.svelte';

    let {
        variant = 'secondary',
        size = 'md',
        icon = '',
        busy = false,
        disabled = false,
        type = 'button',
        title = '',
        href = '',
        class: className = '',
        onclick,
        children,
    }: {
        variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'success';
        size?: 'sm' | 'md' | 'lg';
        icon?: string;
        busy?: boolean;
        disabled?: boolean;
        type?: 'button' | 'submit';
        title?: string;
        href?: string;
        class?: string;
        onclick?: (e: MouseEvent) => void;
        children?: Snippet;
    } = $props();

    const variants = {
        primary: 'bg-accent text-accent-fg border-transparent hover:brightness-110',
        success: 'bg-ok text-white border-transparent hover:brightness-110',
        secondary: 'bg-surface text-fg border-line hover:bg-surface-2',
        danger: 'bg-surface text-fail border-line hover:bg-fail-bg',
        ghost: 'bg-transparent text-muted border-transparent hover:bg-surface-2 hover:text-fg',
    };
    const sizes = {
        sm: 'h-8 px-2.5 text-sm gap-1.5',
        md: 'h-10 px-3.5 text-sm gap-2',
        lg: 'h-12 px-5 text-base gap-2',
    };
    let classes = $derived(
        `inline-flex items-center justify-center rounded-lg border font-medium transition select-none whitespace-nowrap disabled:opacity-50 disabled:pointer-events-none ${variants[variant]} ${sizes[size]} ${className}`,
    );
</script>

{#if href}
    <a {href} class={classes} {title}>
        {#if icon}<Icon name={icon} size={size === 'sm' ? 15 : 17} />{/if}
        {@render children?.()}
    </a>
{:else}
    <button {type} class={classes} disabled={disabled || busy} {title} aria-label={title || undefined} {onclick}>
        {#if busy}
            <span class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
        {:else if icon}
            <Icon name={icon} size={size === 'sm' ? 15 : 17} />
        {/if}
        {@render children?.()}
    </button>
{/if}
