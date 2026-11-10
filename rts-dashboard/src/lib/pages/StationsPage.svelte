<script lang="ts">
    import { api } from '../api';
    import RtsEditor from '../components/RtsEditor.svelte';
    import TrackingEditor from '../components/TrackingEditor.svelte';
    import Badge from '../components/ui/Badge.svelte';
    import Button from '../components/ui/Button.svelte';
    import Icon from '../components/ui/Icon.svelte';
    import Menu from '../components/ui/Menu.svelte';
    import { clock } from '../clock.svelte';
    import { confirm } from '../confirm.svelte';
    import { EDM_MEASUREMENT_MODES, fmtDuration, PRISM_TYPES, rtsColor, units } from '../format';
    import { store } from '../store.svelte';
    import { toast } from '../toast.svelte';
    import type { RTS } from '../types';

    let editorOpen = $state(false);
    let editing = $state<RTS | null>(null);
    let trackingOpen = $state(false);
    let trackingRts = $state<RTS | null>(null);

    function edit(rts: RTS | null) {
        editing = rts;
        editorOpen = true;
    }

    async function remove(rts: RTS) {
        const ok = await confirm({
            title: `Remove ${rts.name}?`,
            message: 'The station is removed from the session. Its jobs and measurements stay available in the history.',
            confirm: 'Remove',
            danger: true,
        });
        if (!ok) return;
        try {
            await api.deleteRts(rts.id);
            store.rts = await api.rtsList(store.session!.id);
            toast.ok(`${rts.name} removed`);
        } catch (e) {
            toast.error((e as Error).message);
        }
    }

    function deviceOnline(id: string | null): boolean | null {
        if (!id || !store.board) return null;
        const d = store.board.devices.find((x) => x.device_id === id);
        return d ? d.online : false;
    }
</script>

<div class="mb-4 flex flex-wrap items-center gap-2">
    <div class="mr-auto">
        <h1 class="text-xl font-bold">Total stations</h1>
        <p class="text-sm text-muted">Connection, station setup and calibration of each instrument.</p>
    </div>
    <Button variant="primary" icon="plus" onclick={() => edit(null)}>Add total station</Button>
</div>

{#if store.devices.length === 0}
    <div class="mb-4 flex items-start gap-3 rounded-xl border border-warn/40 bg-warn-bg p-4 text-sm">
        <Icon name="info" class="mt-0.5 text-warn" />
        <p>No worker device has registered yet. Start the worker on the Raspberry Pi connected to the total station; it registers itself automatically.</p>
    </div>
{/if}

<div class="grid gap-3 md:grid-cols-2">
    {#each store.rts as rts, index (rts.id)}
        {@const online = deviceOnline(rts.device_id)}
        {@const report = rts.instrument_report}
        <article class="rounded-xl border border-line bg-surface p-4 shadow-sm">
            <header class="flex items-start gap-3">
                <span class="mt-1.5 h-3 w-3 shrink-0 rounded-full" style="background: {rtsColor(index)}"></span>
                <div class="min-w-0 flex-1">
                    <h2 class="truncate font-semibold">{rts.name}</h2>
                    <p class="text-xs text-muted">
                        {store.deviceLabel(rts.device_id)} · {rts.port} · {rts.baudrate} baud
                    </p>
                </div>
                {#if online === true}<Badge tone="ok">Device online</Badge>
                {:else if online === false}<Badge tone="fail">Device offline</Badge>
                {:else if !rts.device_id}<Badge tone="warn">No device</Badge>{/if}
            </header>

            <dl class="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
                <div><dt class="text-xs text-muted">Easting</dt><dd class="tabular">{rts.station_x.toFixed(4)} m</dd></div>
                <div><dt class="text-xs text-muted">Northing</dt><dd class="tabular">{rts.station_y.toFixed(4)} m</dd></div>
                <div><dt class="text-xs text-muted">Height</dt><dd class="tabular">{rts.station_z.toFixed(4)} m</dd></div>
                <div><dt class="text-xs text-muted">Orientation</dt><dd class="tabular">{units.radToGon(rts.orientation).toFixed(4)} gon</dd></div>
                <div><dt class="text-xs text-muted">Intrinsic / ext. delay</dt><dd class="tabular">{(rts.internal_delay * 1000).toFixed(2)} / {(rts.external_delay * 1000).toFixed(2)} ms</dd></div>
                <div><dt class="text-xs text-muted">Prism · EDM</dt><dd class="truncate">{PRISM_TYPES[rts.tracking.prism_type] ?? '?'} · {EDM_MEASUREMENT_MODES[rts.tracking.edm_measurement_mode] ?? '?'}</dd></div>
            </dl>

            {#if report}
                <div class="mt-3 rounded-lg bg-surface-2 px-3 py-2 text-xs text-muted">
                    {#if report.ok}
                        {report.instrument_name ?? 'Instrument'}{report.serial_number ? ` #${report.serial_number}` : ''}{report.software_version ? ` · FW ${report.software_version}` : ''}
                        {#if report.battery_capacity != null} · battery {report.battery_capacity} %{/if}
                        · checked {fmtDuration(clock.server - report.received_at)} ago
                    {:else}
                        <span class="text-fail">Last instrument check failed: {report.errors.join('; ')}</span>
                    {/if}
                </div>
            {/if}

            <footer class="mt-4 flex flex-wrap items-center gap-2">
                <Button icon="edit" onclick={() => edit(rts)}>Edit</Button>
                <Button icon="sliders" onclick={() => ((trackingRts = rts), (trackingOpen = true))}>Tracking settings</Button>
                <div class="ml-auto">
                    <Menu
                        items={[
                            { label: 'Instrument check', icon: 'battery', onclick: () => store.startJob(rts.id, 'health_check') },
                            { label: 'Beep test', icon: 'bell', onclick: () => store.startJob(rts.id, 'test_connection') },
                            { label: 'Remove from session', icon: 'trash', danger: true, onclick: () => remove(rts) },
                        ]}
                    />
                </div>
            </footer>
        </article>
    {/each}
</div>

<RtsEditor bind:open={editorOpen} rts={editing} />
<TrackingEditor bind:open={trackingOpen} rts={trackingRts} />
