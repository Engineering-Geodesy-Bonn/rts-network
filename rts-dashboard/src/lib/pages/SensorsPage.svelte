<!-- Sensors: external sensors (live state, recording, downloads), their tracks and the time synchronization. -->
<script lang="ts">
    import { api, apiBase, download } from '../api';
    import PlanPlot, { type PlanTrack } from '../components/plots/PlanPlot.svelte';
    import TimePlot, { type TimeSeries } from '../components/plots/TimePlot.svelte';
    import SyncPanel from '../components/SyncPanel.svelte';
    import Button from '../components/ui/Button.svelte';
    import Panel from '../components/ui/Panel.svelte';
    import Tag from '../components/ui/Tag.svelte';
    import { confirm } from '../confirm.svelte';
    import { fmtAgo, fmtCount } from '../format';
    import { sensorColor, sensorStore } from '../sensors.svelte';
    import { toast } from '../toast.svelte';
    import type { ExternalSensor } from '../types';

    $effect(() => sensorStore.use(true));

    let sensors = $derived(sensorStore.sensors);
    let tracks = $derived(sensorStore.tracks);
    let redraws = 0;
    let version = $derived.by(() => {
        void tracks;
        return ++redraws; // new data: redraw the plots
    });

    async function update(sensor: ExternalSensor, data: { name?: string; logging_active?: boolean }) {
        try {
            await api.updateExternalSensor(sensor.id, data);
            await sensorStore.refresh(true);
            if (data.logging_active !== undefined) toast.ok(`${sensor.name}: recording ${data.logging_active ? 'started' : 'stopped'}`);
        } catch (e) {
            toast.error((e as Error).message);
        }
    }

    async function remove(sensor: ExternalSensor) {
        const ok = await confirm({
            title: `Delete “${sensor.name}”?`,
            message: `The ${fmtCount(sensor.count)} recorded positions are deleted permanently. The sensor appears again when it streams.`,
            confirm: 'Delete',
            danger: true,
        });
        if (!ok) return;
        try {
            await api.deleteExternalSensor(sensor.id);
            await sensorStore.refresh(true);
        } catch (e) {
            toast.error((e as Error).message);
        }
    }

    function position(s: ExternalSensor): string {
        if (s.geodetic) return `${s.geodetic[0].toFixed(7)}° ${s.geodetic[1].toFixed(7)}° ${s.geodetic[2].toFixed(2)} m`;
        if (s.position) return s.position.map((v) => v.toFixed(3)).join(' / ');
        return '–';
    }

    function sensorState(s: ExternalSensor): { text: string; tone: 'good' | 'bad' | 'neutral' } {
        if (s.online) return { text: 'Online', tone: 'good' };
        if (s.last_seen) return { text: `Offline · ${fmtAgo(s.last_seen)}`, tone: 'bad' };
        return { text: 'Never seen', tone: 'neutral' };
    }

    let streamUrl = $derived.by(() => {
        const base = apiBase();
        const http = /^https?:\/\//.test(base) ? base : `${location.protocol}//${location.host}${base}`;
        return http.replace(/^http/, 'ws') + '/ws/external_sensors';
    });

    let named = $derived(
        tracks
            .map((tr) => ({ tr, index: sensorStore.sensorIndex(tr.sensor_id) }))
            .filter(({ index }) => index >= 0)
            .map(({ tr, index }) => ({ tr, name: sensors[index].name, color: sensorColor(index), online: sensors[index].online })),
    );
    let plan = $derived<PlanTrack[]>(named.map(({ tr, name, color, online }) => ({ label: name, color, x: tr.e, y: tr.n, station: null, current: online, stale: !online })));
    let speedSeries = $derived<TimeSeries[]>(named.map(({ tr, name, color }) => ({ label: name, color, t: tr.t, y: tr.speed })));
    let heightSeries = $derived<TimeSeries[]>(named.map(({ tr, name, color }) => ({ label: name, color, t: tr.t, y: tr.u })));
    let anyLocal = $derived(named.some(({ tr }) => tr.local));
</script>

{#snippet recording(s: ExternalSensor)}
    <label class="inline-flex cursor-pointer items-center gap-2">
        <input type="checkbox" class="peer sr-only" checked={s.logging_active} onchange={(e) => update(s, { logging_active: (e.currentTarget as HTMLInputElement).checked })} />
        <span class="relative h-5 w-9 rounded-full bg-line-strong transition peer-checked:bg-bad after:absolute after:top-0.5 after:left-0.5 after:h-4 after:w-4 after:rounded-full after:bg-surface after:transition peer-checked:after:translate-x-4"></span>
        <span class="text-xs font-semibold {s.logging_active ? 'text-bad' : 'text-muted'}">{s.logging_active ? 'REC' : 'Not recording'}</span>
    </label>
{/snippet}

{#snippet tools(s: ExternalSensor)}
    <Button size="sm" icon="download" disabled={s.count === 0} title="Recorded positions as trajectory" onclick={() => download(`/external-sensors/${s.id}/trajectory`, `${s.name}.traj`).catch((e) => toast.error(e.message))}>.traj</Button>
    <Button size="sm" variant="quiet" icon="trash" title="Delete sensor and its recorded positions" onclick={() => remove(s)} />
{/snippet}

<div class="space-y-4">
    <Panel title="External sensors" flush>
        {#snippet actions()}<span class="text-xs text-muted">Appear automatically when they stream positions</span>{/snippet}
        {#if !sensorStore.loaded}
            <p class="px-3 py-8 text-center text-muted">Loading …</p>
        {:else if sensors.length === 0}
            <div class="px-4 py-6 text-[13px]">
                <p class="font-semibold">No external sensor has connected yet.</p>
                <p class="mt-1 text-muted">
                    A sensor (e.g. a GNSS receiver with <span class="num">external-sensors/ublox_gnss</span>) streams one JSON message per position to
                </p>
                <p class="num mt-2 rounded-[5px] bg-surface-2 px-3 py-2 break-all">{streamUrl}</p>
                <p class="num mt-2 rounded-[5px] bg-surface-2 px-3 py-2 break-all">{'{"t": 1731400000.12, "x": 4013250.1, "y": 497812.4, "z": 4912345.6, "vx": 0, "vy": 0, "vz": 0, "epsg": 4978}'}</p>
                <p class="mt-2 text-muted">t is the Unix time in seconds, positions in metres. Every IP address is one sensor.</p>
            </div>
        {:else}
            <!-- phones: one card per sensor -->
            <ul class="divide-y divide-line sm:hidden">
                {#each sensors as s, i (s.id)}
                    {@const st = sensorState(s)}
                    <li class="space-y-2 px-3 py-3">
                        <div class="flex items-center gap-2">
                            <span class="h-8 w-1 shrink-0 rounded-sm" style="background: {sensorColor(i)}"></span>
                            <input class="min-w-0 flex-1 !py-1 font-semibold" value={s.name} aria-label="Name" onchange={(e) => update(s, { name: (e.currentTarget as HTMLInputElement).value })} />
                            <Tag tone={st.tone} text={st.text} />
                        </div>
                        <div class="num flex flex-wrap gap-x-4 text-xs text-muted">
                            <span>{s.ip}</span>
                            {#if s.online}<span>{s.rate_hz?.toFixed(1)} Hz</span><span>{s.speed?.toFixed(2)} m/s</span>{/if}
                            <span>{fmtCount(s.count)} recorded</span>
                        </div>
                        <div class="num text-xs">{position(s)}</div>
                        <div class="flex items-center justify-between">{@render recording(s)}<span>{@render tools(s)}</span></div>
                    </li>
                {/each}
            </ul>
            <div class="hidden overflow-x-auto sm:block">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Sensor</th>
                            <th>State</th>
                            <th class="r">Rate [Hz]</th>
                            <th class="r">Speed [m/s]</th>
                            <th>Last position</th>
                            <th>Recording</th>
                            <th class="r">Recorded</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        {#each sensors as s, i (s.id)}
                            {@const st = sensorState(s)}
                            <tr>
                                <td>
                                    <span class="flex items-center gap-2">
                                        <span class="h-4 w-1 shrink-0 rounded-sm" style="background: {sensorColor(i)}"></span>
                                        <span>
                                            <input class="!w-44 !py-1 font-semibold" value={s.name} aria-label="Name" onchange={(e) => update(s, { name: (e.currentTarget as HTMLInputElement).value })} />
                                            <span class="num block text-xs text-muted">{s.ip}{s.epsg != null ? ` · EPSG ${s.epsg}` : ''}</span>
                                        </span>
                                    </span>
                                </td>
                                <td><Tag tone={st.tone} text={st.text} /></td>
                                <td class="r num">{s.online && s.rate_hz != null ? s.rate_hz.toFixed(1) : '–'}</td>
                                <td class="r num">{s.online && s.speed != null ? s.speed.toFixed(2) : '–'}</td>
                                <td class="num text-xs">{position(s)}</td>
                                <td>
                                    {@render recording(s)}
                                </td>
                                <td class="r num">{fmtCount(s.count)}</td>
                                <td class="r whitespace-nowrap">
                                    {@render tools(s)}
                                </td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            </div>
            <p class="border-t border-line px-3 py-2 text-xs text-muted">
                Live values and the synchronization use every position. Positions are only stored while recording is on. Sensors are shared by all sessions.
            </p>
        {/if}
    </Panel>

    <SyncPanel />

    {#if named.length > 0}
        <Panel title="Live tracks (last 2 min)" flush>
            {#snippet actions()}{#if anyLocal}<span class="text-xs text-muted">GNSS positions in east/north/up around each sensor's first position</span>{/if}{/snippet}
            <div class="grid grid-cols-1 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] [&>*]:min-w-0">
                <div class="border-b border-line p-2 lg:border-r lg:border-b-0">
                    <div class="label px-1 pb-1">Plan [E/N]</div>
                    <PlanPlot tracks={plan} {version} height={330} />
                </div>
                <div class="p-2">
                    <TimePlot series={speedSeries} {version} yLabel="Speed [m/s]" height={150} showX={false} syncKey="sensor-tracks" />
                    <TimePlot series={heightSeries} {version} yLabel="Up [m]" height={170} syncKey="sensor-tracks" />
                </div>
            </div>
        </Panel>
    {/if}
</div>
