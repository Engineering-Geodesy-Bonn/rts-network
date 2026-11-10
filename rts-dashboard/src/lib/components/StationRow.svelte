<script lang="ts">
    import { clock } from '../clock.svelte';
    import { confirm } from '../confirm.svelte';
    import { fmtClock, fmtCount, fmtDateTime, fmtShortDuration, JOB_TYPE_LABEL } from '../format';
    import type { JobSeries } from '../live.svelte';
    import { href } from '../router.svelte';
    import { store } from '../store.svelte';
    import type { Job, RTS } from '../types';
    import { TRACKING_TYPES } from '../types';
    import Button from './ui/Button.svelte';
    import Menu from './ui/Menu.svelte';

    let { rts, color, lastJob, series }: { rts: RTS; color: string; lastJob: Job | undefined; series: JobSeries | undefined } = $props();

    let active = $derived(store.activeJobsOf(rts.id));
    let running = $derived(active.find((j) => j.status === 'running' || j.status === 'lost'));
    let pending = $derived(active.find((j) => j.status === 'pending'));
    let tracking = $derived(!!running && TRACKING_TYPES.includes(running.type));
    let busy = $state(false);

    let lastT = $derived.by(() => {
        void series?.version;
        return tracking ? (series?.lastT ?? null) : null;
    });
    let age = $derived(lastT !== null ? clock.server - lastT : null);
    let rate = $derived(store.health?.stations.find((s) => s.rts_id === rts.id)?.rate_hz ?? null);
    let points = $derived(series?.total ?? running?.count ?? 0);
    let elapsed = $derived(running?.started_at ? clock.server - running.started_at : null);

    type Line = { text: string; tone: 'good' | 'warn' | 'bad' | 'muted' };
    let status = $derived.by((): Line => {
        if (running?.status === 'lost') return { text: 'No contact', tone: 'bad' };
        if (running?.stop_requested) return { text: 'Stopping…', tone: 'muted' };
        if (tracking) {
            if (age === null) return { text: 'Starting…', tone: 'muted' };
            if (age > 10) return { text: `No data for ${fmtShortDuration(age)}`, tone: 'bad' };
            if (age > 2) return { text: 'Data delayed', tone: 'warn' };
            return { text: 'Measuring', tone: 'good' };
        }
        if (running) return { text: `${JOB_TYPE_LABEL[running.type]}…`, tone: 'muted' };
        if (pending) return { text: `Waiting for its device (${JOB_TYPE_LABEL[pending.type].toLowerCase()})`, tone: 'muted' };
        return { text: 'Idle', tone: 'muted' };
    });

    const TONE = { good: 'text-good', warn: 'text-warn', bad: 'text-bad', muted: 'text-muted' };

    async function run(type: Job['type']) {
        busy = true;
        await store.startJob(rts.id, type);
        busy = false;
    }

    async function stop() {
        const job = running ?? pending;
        if (!job) return;
        if (running) {
            const ok = await confirm({
                title: `Stop ${rts.name}?`,
                message: 'The total station stops measuring. Everything measured so far is kept.',
                confirm: 'Stop',
                danger: true,
            });
            if (!ok) return;
        }
        await store.stopJob(job);
    }

    let menu = $derived([
        { label: 'Static measurement', disabled: !!running || !!pending, onclick: () => run('add_static_measurement') },
        { label: 'Check instrument (battery, connection)', disabled: !!running || !!pending, onclick: () => run('health_check') },
        { label: 'Change face', disabled: !!running || !!pending, onclick: () => run('change_face') },
        { label: 'Turn to target', disabled: !!running || !!pending, onclick: () => run('turn_to_target') },
        { label: 'Beep', disabled: !!running || !!pending, onclick: () => run('test_connection') },
    ]);
</script>

<li class="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-line py-4 pr-3 pl-5 last:border-b-0">
    <div class="flex min-w-48 flex-1 items-start gap-3">
        <span class="mt-1 h-10 w-1.5 shrink-0 rounded-full" style="background: {color}"></span>
        <div class="min-w-0">
            <p class="truncate text-[17px] font-semibold">{rts.name}</p>
            <p class="font-medium {TONE[status.tone]}">{status.text}</p>
        </div>
    </div>

    <div class="num min-w-56 flex-1 text-muted">
        {#if tracking}
            <span class="text-fg">{rate !== null && age !== null && age <= 2 ? `${rate.toFixed(0)} Hz` : '– Hz'}</span>
            <span class="mx-1.5 text-faint">·</span>{fmtCount(points)} points
            <span class="mx-1.5 text-faint">·</span>{fmtShortDuration(elapsed)}
        {:else if lastJob && lastJob.count > 0}
            Last measured
            <a class="text-fg underline decoration-line underline-offset-4 hover:decoration-fg" href={href(rts.session_id, 'data', lastJob.id)}>
                {fmtDateTime(lastJob.started_at ?? lastJob.created_at).startsWith('Today') ? fmtClock(lastJob.started_at ?? lastJob.created_at, false) : fmtDateTime(lastJob.started_at ?? lastJob.created_at)}
            </a>
            <span class="mx-1.5 text-faint">·</span>{fmtCount(lastJob.count)} points
        {:else}
            Not measured yet
        {/if}
    </div>

    <div class="flex items-center gap-1">
        {#if running || pending}
            <Button variant="stop" icon="stop" class="w-28" onclick={stop} disabled={!!running?.stop_requested && running.status !== 'lost'}>
                {running ? 'Stop' : 'Cancel'}
            </Button>
        {:else}
            <Button variant="start" icon="play" class="w-28" {busy} onclick={() => run('track_prism')}>Start</Button>
        {/if}
        <Menu items={menu} label="More actions for {rts.name}" />
    </div>
</li>
