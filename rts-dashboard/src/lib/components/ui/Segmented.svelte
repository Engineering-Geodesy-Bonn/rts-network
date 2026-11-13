<script lang="ts" generics="T extends string | number | boolean">
    let {
        options,
        value = $bindable(),
        label,
        onchange,
        class: className = '',
    }: { options: { value: T; label: string }[]; value: T; label: string; onchange?: (value: T) => void; class?: string } = $props();
</script>

<div class="inline-flex overflow-hidden rounded-[5px] border border-line-strong {className}" role="radiogroup" aria-label={label}>
    {#each options as o, i (String(o.value))}
        <button
            role="radio"
            aria-checked={value === o.value}
            class="flex-1 px-3 py-2 text-[13px] font-medium whitespace-nowrap md:flex-none md:px-2.5 md:py-1 md:text-xs {i > 0 ? 'border-l border-line-strong' : ''} {value === o.value ? 'bg-fg text-surface' : 'bg-surface text-muted hover:text-fg'}"
            onclick={() => {
                value = o.value;
                onchange?.(o.value);
            }}>{o.label}</button
        >
    {/each}
</div>
