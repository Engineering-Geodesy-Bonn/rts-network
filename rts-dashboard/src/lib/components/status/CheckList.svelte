<script lang="ts">
    import type { StatusCheck } from "../../api/types";
    import { STATUS_ICON, STATUS_PILL, STATUS_TEXT } from "../../status";

    let { checks }: { checks: StatusCheck[] } = $props();
</script>

<ul class="divide-y divide-slate-700/60">
    {#each checks as c (c.key)}
        <li class="flex items-start gap-2.5 py-1.5 text-sm">
            <span
                class="mt-0.5 w-5 h-5 shrink-0 rounded-full border flex items-center justify-center text-[11px] font-bold {STATUS_PILL[
                    c.status
                ]}"
                title={c.status}>{STATUS_ICON[c.status]}</span
            >
            <div class="min-w-0 flex-1 sm:flex sm:gap-3">
                <span class="font-medium text-slate-200 sm:w-48 sm:shrink-0"
                    >{c.label}</span
                >
                <span
                    class="block break-words {c.status === 'ok'
                        ? 'text-slate-400'
                        : STATUS_TEXT[c.status]}">{c.message}</span
                >
            </div>
        </li>
    {/each}
</ul>
