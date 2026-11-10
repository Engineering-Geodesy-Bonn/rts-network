<script lang="ts">
    import { STATUS_LABEL, STATUS_RANK } from '../format';
    import type { CheckStatus, StatusCheck } from '../types';
    import Icon from './ui/Icon.svelte';

    let { checks, onlyProblems = false }: { checks: StatusCheck[]; onlyProblems?: boolean } = $props();

    const ICON: Record<CheckStatus, string> = { ok: 'check', info: 'info', unknown: 'info', warn: 'alert', fail: 'x' };
    const COLOR: Record<CheckStatus, string> = { ok: 'text-ok', info: 'text-info', unknown: 'text-unknown', warn: 'text-warn', fail: 'text-fail' };

    let shown = $derived(
        [...checks]
            .filter((c) => !onlyProblems || STATUS_RANK[c.status] >= STATUS_RANK.unknown)
            .sort((a, b) => STATUS_RANK[b.status] - STATUS_RANK[a.status]),
    );
</script>

<ul class="divide-y divide-line">
    {#each shown as c (c.key)}
        <li class="flex items-start gap-2.5 py-2 text-sm">
            <Icon name={ICON[c.status]} size={16} class="mt-0.5 {COLOR[c.status]}" />
            <span class="w-40 shrink-0 font-medium">{c.label}</span>
            <span class="min-w-0 flex-1 text-muted">{c.message}</span>
            <span class="sr-only">{STATUS_LABEL[c.status]}</span>
        </li>
    {/each}
</ul>
