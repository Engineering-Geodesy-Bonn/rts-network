<script lang="ts">
    import type { Snippet } from 'svelte';

    let {
        title = '',
        class: className = '',
        flush = false,
        actions,
        children,
    }: { title?: string; class?: string; flush?: boolean; actions?: Snippet; children: Snippet } = $props();
</script>

<section class="panel overflow-hidden {className}">
    {#if title || actions}
        <header class="flex min-h-10 flex-wrap items-center gap-x-3 gap-y-2 border-b border-line bg-surface-2 px-3 py-1.5">
            {#if title}<h2 class="label mr-auto">{title}</h2>{/if}
            {@render actions?.()}
        </header>
    {/if}
    <div class={flush ? '' : 'p-3'}>
        {@render children()}
    </div>
</section>
