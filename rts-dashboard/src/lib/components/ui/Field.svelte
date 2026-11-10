<script lang="ts">
    import type { Snippet } from 'svelte';

    let { label, unit = '', hint = '', class: className = '', children }: { label: string; unit?: string; hint?: string; class?: string; children: Snippet } = $props();
</script>

<label class="block {className}">
    <span class="mb-1.5 block text-sm font-medium">{label}{#if unit}<span class="font-normal text-muted">{` (${unit})`}</span>{/if}</span>
    {@render children()}
    {#if hint}<span class="mt-1 block text-sm text-muted">{hint}</span>{/if}
</label>
