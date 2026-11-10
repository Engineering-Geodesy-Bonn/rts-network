<script lang="ts" generics="T extends string | number">
    let { options, value = $bindable(), label }: { options: { value: T; label: string }[]; value: T; label: string } = $props();
</script>

<div class="inline-flex rounded-lg bg-surface-2 p-1" role="radiogroup" aria-label={label}>
    {#each options as o (o.value)}
        <button
            role="radio"
            aria-checked={value === o.value}
            class="rounded-md px-3 py-1 text-sm font-medium transition {value === o.value ? 'bg-surface text-fg shadow-sm' : 'text-muted hover:text-fg'}"
            onclick={() => (value = o.value)}>{o.label}</button
        >
    {/each}
</div>
