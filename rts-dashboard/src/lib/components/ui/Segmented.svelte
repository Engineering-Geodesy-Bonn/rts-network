<script lang="ts" generics="T extends string | number">
    let { options, value = $bindable(), label }: { options: { value: T; label: string }[]; value: T; label: string } = $props();
</script>

<div class="inline-flex overflow-hidden rounded-[5px] border border-line-strong" role="radiogroup" aria-label={label}>
    {#each options as o, i (o.value)}
        <button
            role="radio"
            aria-checked={value === o.value}
            class="px-2.5 py-1 text-xs font-medium {i > 0 ? 'border-l border-line-strong' : ''} {value === o.value ? 'bg-fg text-surface' : 'bg-surface text-muted hover:text-fg'}"
            onclick={() => (value = o.value)}>{o.label}</button
        >
    {/each}
</div>
