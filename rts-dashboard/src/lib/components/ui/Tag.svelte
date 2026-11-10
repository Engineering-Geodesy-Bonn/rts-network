<!-- Compact status tag: colored text on a soft background, uppercase -->
<script lang="ts">
    let { tone = 'neutral', text }: { tone?: 'good' | 'warn' | 'bad' | 'neutral' | 'accent'; text: string } = $props();
    const TONES = {
        good: 'bg-good-soft text-good',
        warn: 'bg-warn-soft text-warn',
        bad: 'bg-bad-soft text-bad',
        neutral: 'bg-surface-2 text-muted',
        accent: 'bg-surface-2 text-accent',
    };
</script>

<span class="inline-block rounded-[3px] px-1.5 py-px text-[11px] font-semibold tracking-wide uppercase whitespace-nowrap {TONES[tone]}">{text}</span>
