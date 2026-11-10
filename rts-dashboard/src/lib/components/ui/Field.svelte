<script lang="ts">
    import type { Snippet } from 'svelte';

    let {
        label,
        hint = '',
        unit = '',
        class: className = '',
        children,
    }: { label: string; hint?: string; unit?: string; class?: string; children: Snippet } = $props();
</script>

<label class="block {className}">
    <span class="mb-1 flex items-baseline justify-between gap-2 text-xs font-medium text-muted">
        <span>{label}</span>
        {#if unit}<span class="font-normal">{unit}</span>{/if}
    </span>
    {@render children()}
    {#if hint}<span class="mt-1 block text-xs text-muted">{hint}</span>{/if}
</label>
