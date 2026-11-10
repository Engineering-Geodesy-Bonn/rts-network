<script lang="ts">
    import type { Snippet } from 'svelte';

    let { label, unit = '', hint = '', class: className = '', children }: { label: string; unit?: string; hint?: string; class?: string; children: Snippet } = $props();
</script>

<label class="block {className}">
    <span class="label mb-1 block">{label}{#if unit}<span class="font-normal normal-case tracking-normal">{` [${unit}]`}</span>{/if}</span>
    {@render children()}
    {#if hint}<span class="mt-1 block text-xs text-muted">{hint}</span>{/if}
</label>
