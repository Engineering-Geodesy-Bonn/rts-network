<script lang="ts">
    import type { Snippet } from 'svelte';
    import type { CheckStatus } from '../../types';

    let {
        tone = 'unknown',
        pulse = false,
        class: className = '',
        children,
    }: { tone?: CheckStatus; pulse?: boolean; class?: string; children: Snippet } = $props();

    const tones: Record<CheckStatus, string> = {
        ok: 'bg-ok-bg text-ok',
        warn: 'bg-warn-bg text-warn',
        fail: 'bg-fail-bg text-fail',
        info: 'bg-info-bg text-info',
        unknown: 'bg-unknown-bg text-unknown',
    };
    const dots: Record<CheckStatus, string> = {
        ok: 'bg-ok',
        warn: 'bg-warn',
        fail: 'bg-fail',
        info: 'bg-info',
        unknown: 'bg-unknown',
    };
</script>

<span class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold whitespace-nowrap {tones[tone]} {className}">
    <span class="relative flex h-2 w-2">
        {#if pulse}<span class="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 {dots[tone]}"></span>{/if}
        <span class="relative inline-flex h-2 w-2 rounded-full {dots[tone]}"></span>
    </span>
    {@render children()}
</span>
