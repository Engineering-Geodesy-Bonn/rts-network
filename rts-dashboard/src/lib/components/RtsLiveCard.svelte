<script lang="ts">
    import { clock } from '../clock.svelte';
    import { confirm } from '../confirm.svelte';
    import { fmtClock, fmtCount, fmtDuration, fmtShortDuration, JOB_STATUS_LABEL, JOB_TYPE_LABEL, STATUS_RANK } from '../format';
    import type { JobSeries } from '../live.svelte';
    import { href } from '../router.svelte';
    import { store } from '../store.svelte';
    import type { CheckStatus, Job, RTS, RTSBoardEntry } from '../types';
    import { TRACKING_TYPES } from '../types';
    import Badge from './ui/Badge.svelte';
    import Button from './ui/Button.svelte';
    import Icon from './ui/Icon.svelte';
    import Menu from './ui/Menu.svelte';

    let {
        rts,
        color,
        job,
        series,
        board,
    }: { rts: RTS; color: string; job: Job | undefined; series: JobSeries | undefined; board: RTSBoardEntry | undefined } = $props();

    let active = $derived(store.activeJobsOf(rts.id));
    let running = $derived(active.find((j) => j.status === 'running' || j.status === 'lost'));
    let pending = $derived(active.filter((j) => j.status === 'pending'));
    let tracking = $derived(running !== undefined && TRACKING_TYPES.includes(running.type));
    let starting = $state(false);

    // live metrics from the data in the browser
    let lastT = $derived.by(() => {
        void series?.version;
        return series?.lastT ?? null;
    });
    let age = $derived(lastT !== null ? clock.server - lastT : null);
    let rate = $derived.by(() => {
        void series?.version;
        if (!series || !tracking || lastT === null) return null;
        const i = series.indexAt(lastT - 10);
        const n = series.cols.t.length - i;
        const span = lastT - series.cols.t[i];
        return n > 1 && span > 0 ? (n - 1) / span : null;
    });
    let duration = $derived(job?.first_t != null ? ((tracking ? lastT : job.last_t) ?? job.first_t) - job.first_t : null);

    let status = $derived.by((): { label: string; tone: CheckStatus; pulse: boolean } => {
        if (running?.status === 'lost') return { label: 'No contact to worker', tone: 'fail', pulse: true };
        if (running && running.stop_requested) return { label: 'Stopping…', tone: 'info', pulse: true };
        if (tracking) {
            if (age === null) return { label: 'Starting…', tone: 'info', pulse: true };
            if (age > 10) return { label: `No data for ${fmtDuration(age)}`, tone: 'fail', pulse: true };
            if (age > 2) return { label: 'Data delayed', tone: 'warn', pulse: true };
            return { label: 'Tracking', tone: 'ok', pulse: true };
        }
        if (running) return { label: JOB_TYPE_LABEL[running.type] + '…', tone: 'info', pulse: true };
        if (pending.length) return { label: 'Waiting for worker', tone: 'info', pulse: false };
        return { label: 'Idle', tone: 'unknown', pulse: false };
    });

    // problems reported by the status board (most severe first)
    let problems = $derived(
        (board?.checks ?? [])
            .filter((c) => c.status === 'fail' || c.status === 'warn')
            .sort((a, b) => STATUS_RANK[b.status] - STATUS_RANK[a.status])
            .slice(0, 2),
    );

    async function start(type: Job['type']) {
        starting = true;
        await store.startJob(rts.id, type);
        starting = false;
    }

    async function stop() {
        if (!running) return;
        const ok = await confirm({
            title: `Stop ${JOB_TYPE_LABEL[running.type].toLowerCase()} on ${rts.name}?`,
            message: running.status === 'lost'
                ? 'The worker is not reachable. The job is marked as interrupted; measurements still stored on the worker are uploaded when it is back.'
                : 'The total station stops measuring. All measurements recorded so far are kept.',
            confirm: 'Stop',
            danger: true,
        });
        if (ok) await store.stopJob(running);
    }

    let menu = $derived([
        { label: 'Static measurement', icon: 'target', disabled: !!running, onclick: () => start('add_static_measurement') },
        { label: 'Instrument check', icon: 'battery', disabled: !!running, onclick: () => start('health_check') },
        { label: 'Change face', icon: 'flip', disabled: !!running, onclick: () => start('change_face') },
        { label: 'Turn to target', icon: 'crosshair', disabled: !!running, onclick: () => start('turn_to_target') },
        { label: 'Beep test', icon: 'bell', disabled: !!running, onclick: () => start('test_connection') },
        { label: 'Simulated tracking', icon: 'activity', disabled: !!running, onclick: () => start('dummy_tracking') },
        ...pending.map((p) => ({ label: `Cancel ${JOB_TYPE_LABEL[p.type].toLowerCase()}`, icon: 'x', danger: true, onclick: () => store.stopJob(p) })),
    ]);
</script>

<article class="flex flex-col rounded-xl border bg-surface shadow-sm {status.tone === 'fail' ? 'border-fail/60' : 'border-line'}">
    <header class="flex items-start gap-3 px-4 pt-3.5">
        <span class="mt-1.5 h-3 w-3 shrink-0 rounded-full" style="background: {color}"></span>
        <div class="min-w-0 flex-1">
            <h3 class="truncate font-semibold">{rts.name}</h3>
            <p class="truncate text-xs text-muted">{store.deviceLabel(rts.device_id)} · {rts.port}</p>
        </div>
        <Badge tone={status.tone} pulse={status.pulse}>{status.label}</Badge>
    </header>

    {#if tracking || (running && series)}
        <dl class="mt-3 grid grid-cols-4 gap-1 px-4 text-center">
            <div>
                <dt class="text-[11px] uppercase tracking-wide text-muted">Rate</dt>
                <dd class="text-lg font-semibold tabular">{rate !== null ? rate.toFixed(1) : '–'}<span class="text-xs font-normal text-muted"> Hz</span></dd>
            </div>
            <div>
                <dt class="text-[11px] uppercase tracking-wide text-muted">Last</dt>
                <dd class="text-lg font-semibold tabular {age !== null && age > 10 ? 'text-fail' : age !== null && age > 2 ? 'text-warn' : ''}">
                    {age !== null ? (age < 1 ? 'now' : fmtShortDuration(age)) : '–'}
                </dd>
            </div>
            <div>
                <dt class="text-[11px] uppercase tracking-wide text-muted">Points</dt>
                <dd class="text-lg font-semibold tabular">{fmtCount(series?.total ?? running?.count)}</dd>
            </div>
            <div>
                <dt class="text-[11px] uppercase tracking-wide text-muted">Duration</dt>
                <dd class="text-lg font-semibold tabular whitespace-nowrap">{fmtShortDuration(duration)}</dd>
            </div>
        </dl>
    {:else if job}
        <a href={href(rts.session_id, 'jobs', job.id)} class="mx-4 mt-3 block rounded-lg bg-surface-2 px-3 py-2 text-sm hover:brightness-95">
            <span class="text-muted">Last:</span>
            {JOB_TYPE_LABEL[job.type]} · {JOB_STATUS_LABEL[job.status].toLowerCase()}
            {fmtClock(job.finished_at ?? job.created_at, false)} · {fmtCount(job.count)} pts{#if job.first_t != null && job.last_t != null && job.last_t > job.first_t} · {fmtDuration(job.last_t - job.first_t)}{/if}
        </a>
    {:else}
        <p class="mx-4 mt-3 text-sm text-muted">No measurements yet.</p>
    {/if}

    {#if problems.length}
        <ul class="mx-4 mt-3 space-y-1">
            {#each problems as p (p.key)}
                <li class="flex items-start gap-1.5 text-xs {p.status === 'fail' ? 'text-fail' : 'text-warn'}">
                    <Icon name="alert" size={14} class="mt-px" />
                    <span><span class="font-semibold">{p.label}:</span> {p.message}</span>
                </li>
            {/each}
        </ul>
    {/if}

    <footer class="mt-auto flex items-center gap-2 px-4 pt-3 pb-3.5">
        {#if running}
            <Button variant="danger" icon="stop" class="flex-1" onclick={stop} disabled={running.stop_requested && running.status !== 'lost'}>
                Stop
            </Button>
        {:else}
            <Button variant="success" icon="play" class="flex-1" busy={starting} disabled={pending.length > 0} onclick={() => start('track_prism')}>
                {pending.length ? 'Waiting for worker…' : 'Start tracking'}
            </Button>
        {/if}
        <Menu items={menu} />
    </footer>
</article>
