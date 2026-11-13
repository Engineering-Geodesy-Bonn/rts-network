<!--
    One row per station with its live values. Table on wide screens, stacked blocks on phones.
    Values are refreshed with `tick` (a few times per second), not on every message.
-->
<script lang="ts" module>
    import type { JobSeries } from '../live.svelte';
    import type { Job, RTS } from '../types';

    export interface StationEntry {
        rts: RTS;
        color: string;
        series: JobSeries | undefined;
        lastJob: Job | undefined;
    }
</script>

<script lang="ts">
    import { clock } from '../clock.svelte';
    import { confirm } from '../confirm.svelte';
    import { fmtClock, fmtCount, fmtDateTime, JOB_TYPE_LABEL, PRISM_TYPES, units } from '../format';
    import { href } from '../router.svelte';
    import { store } from '../store.svelte';
    import { TRACKING_TYPES } from '../types';
    import TrackingSettingsDialog from './TrackingSettingsDialog.svelte';
    import Button from './ui/Button.svelte';
    import Menu from './ui/Menu.svelte';
    import Tag from './ui/Tag.svelte';

    let { entries, mode, tick }: { entries: StationEntry[]; mode: 'position' | 'polar'; tick: number } = $props();

    let settingsOpen = $state(false);
    let settingsRtsId = $state<string | null>(null);
    // From the store, so that the dialog shows the saved values after a change
    let settingsRts = $derived(store.rtsById(settingsRtsId) ?? null);

    function openSettings(e: StationEntry) {
        settingsRtsId = e.rts.id;
        settingsOpen = true;
    }

    const prism = (rts: RTS) => PRISM_TYPES[rts.tracking.prism_type] ?? `Prism ${rts.tracking.prism_type}`;

    const COLS = {
        position: [
            { key: 'x', label: 'E [m]', digits: 3 },
            { key: 'y', label: 'N [m]', digits: 3 },
            { key: 'z', label: 'H [m]', digits: 3 },
        ],
        polar: [
            { key: 'hz', label: 'Hz [gon]', digits: 4, gon: true },
            { key: 'v', label: 'V [gon]', digits: 4, gon: true },
            { key: 'd', label: 'D [m]', digits: 4 },
        ],
    } as const;

    type Tone = 'good' | 'warn' | 'bad' | 'neutral' | 'accent';

    function view(e: StationEntry) {
        void tick;
        const active = store.activeJobsOf(e.rts.id);
        const running = active.find((j) => j.status === 'running' || j.status === 'lost');
        const pending = active.find((j) => j.status === 'pending');
        const tracking = !!running && TRACKING_TYPES.includes(running.type);
        const health = store.health?.stations.find((s) => s.rts_id === e.rts.id);
        const cols = tracking ? e.series?.cols : undefined;
        const n = cols?.t.length ?? 0;
        const age = n ? Math.max(0, clock.server - cols!.t[n - 1]) : null;
        let state: { text: string; tone: Tone };
        if (running?.status === 'lost') state = { text: 'No contact', tone: 'bad' };
        else if (running?.stop_requested) state = { text: 'Stopping', tone: 'neutral' };
        else if (tracking && age === null) state = { text: 'Starting', tone: 'accent' };
        else if (tracking && age! > 10) state = { text: 'No data', tone: 'bad' };
        else if (tracking && age! > 2) state = { text: 'Delayed', tone: 'warn' };
        else if (tracking) state = { text: 'Measuring', tone: 'good' };
        else if (running) state = { text: JOB_TYPE_LABEL[running.type], tone: 'accent' };
        else if (pending) state = { text: 'Waiting', tone: 'accent' };
        else state = { text: 'Idle', tone: 'neutral' };
        const value = (key: 'x' | 'y' | 'z' | 'hz' | 'v' | 'd', digits: number, gon = false) => {
            if (!n) return '–';
            const v = cols![key][n - 1];
            return v == null ? '–' : (gon ? units.radToGon(v) : v).toFixed(digits);
        };
        const fresh = age !== null && age <= 2;
        return {
            running,
            pending,
            tracking,
            state,
            age,
            rate: fresh && health?.rate_hz != null ? health.rate_hz.toFixed(1) : '–',
            points: tracking ? fmtCount(e.series?.total ?? running?.count) : '–',
            duration: running?.started_at && tracking ? clock.server - running.started_at : null,
            values: COLS[mode].map((c) => value(c.key, c.digits, 'gon' in c)),
            jitter: health?.timing_jitter != null ? (health.timing_jitter * 1000).toFixed(2) : '–',
            battery: health?.battery != null ? String(health.battery) : '–',
        };
    }

    function hms(seconds: number | null): string {
        if (seconds == null) return '–';
        const s = Math.max(0, Math.floor(seconds));
        const pad = (v: number) => String(v).padStart(2, '0');
        return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
    }

    function lastLabel(job: Job | undefined): string {
        if (!job || job.count === 0) return 'Not measured yet';
        const at = job.started_at ?? job.created_at;
        const when = fmtDateTime(at).startsWith('Today') ? fmtClock(at, false) : fmtDateTime(at);
        return `Last measurement ${when} · ${fmtCount(job.count)} points`;
    }

    async function start(e: StationEntry, type: Job['type']) {
        await store.startJob(e.rts.id, type);
    }

    async function stop(e: StationEntry, job: Job, running: boolean) {
        if (running && !(await confirm({ title: `Stop ${e.rts.name}?`, message: 'The total station stops measuring. Everything measured so far is kept.', confirm: 'Stop', danger: true }))) return;
        await store.stopJob(job);
    }

    function menu(e: StationEntry, busy: boolean) {
        return [
            { label: 'Tracking settings…', onclick: () => openSettings(e) },
            { label: 'Static measurement', disabled: busy, onclick: () => start(e, 'add_static_measurement') },
            { label: 'Instrument check (battery, connection)', disabled: busy, onclick: () => start(e, 'health_check') },
            { label: 'Change face', disabled: busy, onclick: () => start(e, 'change_face') },
            { label: 'Turn to target', disabled: busy, onclick: () => start(e, 'turn_to_target') },
            { label: 'Beep', disabled: busy, onclick: () => start(e, 'test_connection') },
        ];
    }
</script>

{#snippet prismLink(e: StationEntry)}
    <button type="button" class="underline decoration-line-strong underline-offset-2 hover:text-fg" title="Tracking settings of {e.rts.name}" onclick={() => openSettings(e)}>{prism(e.rts)}</button>
{/snippet}

{#snippet actions(e: StationEntry, v: ReturnType<typeof view>)}
    <div class="flex items-center justify-end gap-1.5">
        {#if v.running || v.pending}
            <Button variant="stop" icon="stop" disabled={!!v.running?.stop_requested && v.running.status !== 'lost'} onclick={() => stop(e, (v.running ?? v.pending)!, !!v.running)}>
                {v.running ? 'Stop' : 'Cancel'}
            </Button>
        {:else}
            <Button variant="start" icon="play" onclick={() => start(e, 'track_prism')}>Start</Button>
        {/if}
        <Menu items={menu(e, !!v.running || !!v.pending)} label="More actions for {e.rts.name}" note={v.running || v.pending ? 'Measuring actions are available when the station is idle.' : ''} />
    </div>
{/snippet}

<!-- wide screens: table -->
<div class="panel hidden overflow-x-auto lg:block">
    <table class="data-table">
        <thead>
            <tr>
                <th>Station</th>
                <th>State</th>
                <th class="r">Rate [Hz]</th>
                <th class="r">Age [s]</th>
                <th class="r">Points</th>
                <th class="r">Duration</th>
                {#each COLS[mode] as c (c.key)}<th class="r">{c.label}</th>{/each}
                <th class="r">Jitter [ms]</th>
                <th class="r">Batt. [%]</th>
                <th></th>
            </tr>
        </thead>
        <tbody>
            {#each entries as e (e.rts.id)}
                {@const v = view(e)}
                <tr>
                    <td>
                        <div class="flex items-center gap-2.5">
                            <span class="h-7 w-1 rounded-sm" style="background: {e.color}"></span>
                            <div>
                                <div class="font-semibold">{e.rts.name}</div>
                                <div class="text-xs text-muted">{store.deviceLabel(e.rts.device_id)} · {e.rts.port} · {@render prismLink(e)}</div>
                            </div>
                        </div>
                    </td>
                    <td><Tag tone={v.state.tone} text={v.state.text} /></td>
                    {#if v.tracking}
                        <td class="r num">{v.rate}</td>
                        <td class="r num {v.age !== null && v.age > 10 ? 'text-bad' : v.age !== null && v.age > 2 ? 'text-warn' : ''}">{v.age !== null ? v.age.toFixed(1) : '–'}</td>
                        <td class="r num">{v.points}</td>
                        <td class="r num">{hms(v.duration)}</td>
                        {#each v.values as value, i (i)}<td class="r num">{value}</td>{/each}
                        <td class="r num">{v.jitter}</td>
                    {:else}
                        <td colspan={8} class="text-[13px] text-muted">
                            {#if e.lastJob && e.lastJob.count > 0}
                                <a class="underline decoration-line-strong underline-offset-2 hover:text-fg" href={href(e.rts.session_id, 'data', e.lastJob.id)}>{lastLabel(e.lastJob)}</a>
                            {:else}{lastLabel(e.lastJob)}{/if}
                        </td>
                    {/if}
                    <td class="r num">{v.battery}</td>
                    <td>{@render actions(e, v)}</td>
                </tr>
            {/each}
        </tbody>
    </table>
</div>

<!--
    phones and tablets: one card per station. The coordinates are what is watched in the field,
    so they are large; rate, age, points, duration, jitter and battery share one status line.
-->
<div class="panel divide-y divide-line lg:hidden">
    {#each entries as e (e.rts.id)}
        {@const v = view(e)}
        <div class="relative py-3 pr-3 pl-4">
            <span class="absolute inset-y-3 left-0 w-1 rounded-r-sm" style="background: {e.color}"></span>
            <div class="flex items-start gap-2">
                <div class="min-w-0 flex-1">
                    <div class="text-[15px] leading-snug font-semibold break-words">{e.rts.name}</div>
                    <div class="mt-0.5 flex min-w-0 items-center gap-2">
                        <Tag tone={v.state.tone} text={v.state.text} />
                        <span class="truncate text-xs text-muted">{@render prismLink(e)} · {store.deviceLabel(e.rts.device_id)} · {e.rts.port}</span>
                    </div>
                </div>
                {@render actions(e, v)}
            </div>
            {#if v.tracking}
                <dl class="mt-2 grid grid-cols-3 gap-x-3">
                    {#each COLS[mode] as c, i (c.key)}
                        <div class="min-w-0"><dt class="label">{c.label}</dt><dd class="num truncate text-[17px] leading-tight font-semibold">{v.values[i]}</dd></div>
                    {/each}
                </dl>
                <!-- in the columns of E/N/H, so the values do not jump when their width changes -->
                <p class="num mt-2 grid grid-cols-3 gap-x-3 gap-y-0.5 text-xs whitespace-nowrap text-muted">
                    <span><span class="text-fg">{v.rate}</span> Hz</span>
                    <span class={v.age !== null && v.age > 10 ? 'text-bad' : v.age !== null && v.age > 2 ? 'text-warn' : ''}><span class={v.age !== null && v.age > 2 ? '' : 'text-fg'}>{v.age !== null ? v.age.toFixed(1) : '–'}</span> s ago</span>
                    <span><span class="text-fg">{v.points}</span> pts</span>
                    <span class="text-fg">{hms(v.duration)}</span>
                    <span>jitter <span class="text-fg">{v.jitter}</span> ms</span>
                    {#if v.battery !== '–'}<span>batt. <span class="text-fg">{v.battery}</span> %</span>{/if}
                </p>
            {:else}
                <p class="mt-2 text-[13px] text-muted">
                    {#if e.lastJob && e.lastJob.count > 0}
                        <a class="underline decoration-line-strong underline-offset-2" href={href(e.rts.session_id, 'data', e.lastJob.id)}>{lastLabel(e.lastJob)}</a>
                    {:else}{lastLabel(e.lastJob)}{/if}
                    {#if v.battery !== '–'}<span class="num"> · batt. {v.battery} %</span>{/if}
                </p>
            {/if}
        </div>
    {/each}
</div>

<TrackingSettingsDialog bind:open={settingsOpen} rts={settingsRts} />
