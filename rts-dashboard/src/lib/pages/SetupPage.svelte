<script lang="ts">
    import { onMount } from 'svelte';
    import { api, download } from '../api';
    import StationEditor from '../components/StationEditor.svelte';
    import Button from '../components/ui/Button.svelte';
    import Field from '../components/ui/Field.svelte';
    import Modal from '../components/ui/Modal.svelte';
    import Panel from '../components/ui/Panel.svelte';
    import Tag from '../components/ui/Tag.svelte';
    import { confirm } from '../confirm.svelte';
    import { events } from '../events.svelte';
    import { EDM_MEASUREMENT_MODES, fmtBytes, fmtCount, fmtDuration, fmtTime, PRISM_TYPES, rtsColor, units } from '../format';
    import { navigate } from '../router.svelte';
    import { store } from '../store.svelte';
    import { toast } from '../toast.svelte';
    import type { DeviceHealth, ExternalSensor, RTS, SensorRoles, SynchronizerState } from '../types';

    let editorOpen = $state(false);
    let editing = $state<RTS | null>(null);

    function edit(rts: RTS | null) {
        editing = rts;
        editorOpen = true;
    }

    // ── devices ────────────────────────────────────────────────────────
    let deviceHealth = $derived(new Map((store.health?.devices ?? []).map((d) => [d.device_id, d])));
    // devices of this session or online first; old ones only on request
    let relevantDevices = $derived(store.devices.filter((d) => deviceHealth.has(d.id) || store.rts.some((r) => r.device_id === d.id)));
    let otherDevices = $derived(store.devices.filter((d) => !relevantDevices.includes(d)));
    let showOther = $state(false);

    async function forgetDevice(id: string) {
        try {
            await api.deleteDevice(id);
            store.devices = await api.devices();
        } catch (e) {
            toast.error((e as Error).message);
        }
    }

    type Tone = 'good' | 'warn' | 'bad' | 'neutral';
    function deviceState(h: DeviceHealth | undefined): { text: string; tone: Tone } {
        if (!h) return { text: 'Not in use', tone: 'neutral' };
        if (!h.online) return { text: `Offline ${h.last_seen_age != null ? fmtDuration(h.last_seen_age) : ''}`.trim(), tone: 'bad' };
        return { text: 'Online', tone: 'good' };
    }

    const SYNC: Record<DeviceHealth['time_sync'], { text: string; tone: Tone }> = {
        gnss: { text: 'GNSS / PPS', tone: 'good' },
        network: { text: 'Network (NTP)', tone: 'warn' },
        none: { text: 'Not synced', tone: 'bad' },
        unknown: { text: 'Unknown', tone: 'warn' },
    };

    let renaming = $state<{ id: string; name: string } | null>(null);
    let renameOpen = $state(false);

    async function renameDevice() {
        if (!renaming) return;
        try {
            await api.updateDevice(renaming.id, renaming.name.trim() || null);
            store.devices = await api.devices();
            renameOpen = false;
        } catch (e) {
            toast.error((e as Error).message);
        }
    }

    // ── session ────────────────────────────────────────────────────────
    let name = $state(store.session?.name ?? '');
    let notes = $state(store.session?.notes ?? '');
    let exporting = $state(false);

    async function saveSession() {
        if (!store.session || (name.trim() === store.session.name && notes === store.session.notes) || !name.trim()) return;
        try {
            store.session = await api.updateSession(store.session.id, { name: name.trim(), notes });
            toast.ok('Saved');
        } catch (e) {
            toast.error((e as Error).message);
        }
    }

    async function exportAll() {
        exporting = true;
        try {
            toast.ok(`Downloaded ${await download(`/sessions/${store.session!.id}/export`, 'session.zip')}`);
        } catch (e) {
            toast.error((e as Error).message);
        } finally {
            exporting = false;
        }
    }

    async function archive() {
        try {
            store.session = await api.updateSession(store.session!.id, { archived: !store.session!.archived });
            toast.ok(store.session.archived ? 'Session archived' : 'Session restored');
        } catch (e) {
            toast.error((e as Error).message);
        }
    }

    async function deleteSession() {
        const s = store.session!;
        const ok = await confirm({
            title: `Delete “${s.name}”?`,
            message: `All ${fmtCount(s.measurement_count)} measurements of this session are deleted permanently. Download them first if you still need them.`,
            confirm: 'Delete session',
            danger: true,
        });
        if (!ok) return;
        try {
            await api.deleteSession(s.id);
            navigate('#/');
        } catch (e) {
            toast.error((e as Error).message);
        }
    }

    // ── external sensors & synchronizer ────────────────────────────────
    let sensors = $state<ExternalSensor[]>([]);
    let roles = $state<SensorRoles>({ primary_sensor_id: null, secondary_sensor_id: null });
    let sync = $state<SynchronizerState | null>(null);

    async function loadSensors() {
        try {
            [sensors, roles] = await Promise.all([api.externalSensors(), api.syncRoles()]);
        } catch {
            /* shown empty */
        }
    }

    onMount(() => {
        void loadSensors();
        const off = events.on((e) => {
            if (e.type === 'changed' && (e.entity === 'external_sensor' || e.entity === 'synchronizer')) void loadSensors();
        });
        const timer = setInterval(async () => {
            if (roles.primary_sensor_id && roles.secondary_sensor_id) sync = await api.syncState().catch(() => null);
        }, 2000);
        return () => {
            off();
            clearInterval(timer);
        };
    });

    async function updateSensor(id: string, data: { name?: string; logging_active?: boolean }) {
        try {
            await api.updateExternalSensor(id, data);
            await loadSensors();
        } catch (e) {
            toast.error((e as Error).message);
        }
    }

    let syncOptions = $derived([...store.rts.map((r) => ({ id: r.id, label: r.name })), ...sensors.map((s) => ({ id: s.id, label: s.name }))]);
</script>

<div class="space-y-4">
    <Panel title="Total stations" flush>
        {#snippet actions()}<Button variant="primary" icon="plus" onclick={() => edit(null)}>Add station</Button>{/snippet}
        {#if store.rts.length === 0}
            <p class="px-3 py-8 text-center text-muted">No total stations yet. Add one for every instrument you set up.</p>
        {:else}
            <div class="overflow-x-auto">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Station</th>
                            <th>Raspberry Pi</th>
                            <th>Port</th>
                            <th class="r">Baud</th>
                            <th class="r">E [m]</th>
                            <th class="r">N [m]</th>
                            <th class="r">H [m]</th>
                            <th class="r">Orient. [gon]</th>
                            <th class="r">Delay int/ext [ms]</th>
                            <th>Prism · EDM</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        {#each store.rts as rts, index (rts.id)}
                            <tr class="link" onclick={() => edit(rts)}>
                                <td><span class="flex items-center gap-2"><span class="h-4 w-1 rounded-sm" style="background: {rtsColor(index)}"></span><span class="font-semibold">{rts.name}</span></span></td>
                                <td class={rts.device_id ? '' : 'text-bad'}>{rts.device_id ? store.deviceLabel(rts.device_id) : 'Not assigned'}</td>
                                <td class="num">{rts.port}</td>
                                <td class="r num">{rts.baudrate}</td>
                                <td class="r num">{rts.station_x.toFixed(4)}</td>
                                <td class="r num">{rts.station_y.toFixed(4)}</td>
                                <td class="r num">{rts.station_z.toFixed(4)}</td>
                                <td class="r num">{units.radToGon(rts.orientation).toFixed(5)}</td>
                                <td class="r num">{(rts.internal_delay * 1000).toFixed(2)} / {(rts.external_delay * 1000).toFixed(2)}</td>
                                <td class="text-muted">{PRISM_TYPES[rts.tracking.prism_type] ?? '?'} · {EDM_MEASUREMENT_MODES[rts.tracking.edm_measurement_mode] ?? '?'}</td>
                                <td class="r"><span class="text-xs font-medium text-accent">Edit</span></td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            </div>
        {/if}
    </Panel>

    <Panel title="Raspberry Pis" flush>
        {#snippet actions()}<span class="text-xs text-muted">Appear automatically when their worker starts</span>{/snippet}
        {#if relevantDevices.length === 0}
            <p class="px-3 py-8 text-center text-muted">No Raspberry Pi is connected.</p>
        {:else}
            <div class="overflow-x-auto">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Device</th>
                            <th>IP</th>
                            <th>State</th>
                            <th>Time source</th>
                            <th class="r">Clock error</th>
                            <th class="r">Device − server</th>
                            <th class="r">Workers</th>
                            <th>Version</th>
                            <th class="r">CPU [°C]</th>
                            <th class="r">Disk free</th>
                            <th class="r">Unsent</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        {#each relevantDevices as d (d.id)}
                            {@const h = deviceHealth.get(d.id)}
                            {@const state = deviceState(h)}
                            {@const online = !!h?.online}
                            <tr>
                                <td class="font-semibold">{d.name || d.hostname || d.ip}{#if d.name && d.hostname}<span class="font-normal text-muted"> ({d.hostname})</span>{/if}</td>
                                <td class="num">{d.ip}</td>
                                <td><Tag tone={state.tone} text={state.text} /></td>
                                <td>{#if online}<Tag tone={SYNC[h!.time_sync].tone} text={SYNC[h!.time_sync].text} />{:else}–{/if}</td>
                                <td class="r num">{online && h!.time_error != null ? `±${fmtTime(h!.time_error)}` : '–'}</td>
                                <td class="r num">{online && h!.clock_offset != null ? fmtTime(-h!.clock_offset) : '–'}</td>
                                <td class="r num">{online ? h!.workers : '–'}</td>
                                <td class="num">{online ? (h!.version ?? '–') : '–'}</td>
                                <td class="r num">{online && h!.cpu_temperature != null ? h!.cpu_temperature.toFixed(1) : '–'}</td>
                                <td class="r num">{online && h!.disk_free != null ? fmtBytes(h!.disk_free) : '–'}</td>
                                <td class="r num {h?.unsent ? 'text-warn' : ''}">{h ? fmtCount(h.unsent) : '–'}</td>
                                <td class="r"><Button variant="quiet" size="sm" onclick={() => ((renaming = { id: d.id, name: d.name ?? '' }), (renameOpen = true))}>Rename</Button></td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            </div>
        {/if}
        {#if otherDevices.length}
            <div class="border-t border-line px-3 py-2">
                <button class="text-xs text-muted hover:text-fg" onclick={() => (showOther = !showOther)}>
                    {showOther ? 'Hide' : 'Show'} {otherDevices.length} other device{otherDevices.length === 1 ? '' : 's'} (offline, not used in this session)
                </button>
                {#if showOther}
                    <table class="data-table mt-2">
                        <tbody>
                            {#each otherDevices as d (d.id)}
                                <tr>
                                    <td>{d.name || d.hostname || d.ip}</td>
                                    <td class="num text-muted">{d.ip}</td>
                                    <td class="r"><Button variant="quiet" size="sm" onclick={() => forgetDevice(d.id)}>Forget</Button></td>
                                </tr>
                            {/each}
                        </tbody>
                    </table>
                {/if}
            </div>
        {/if}
    </Panel>

    <Panel title="Session">
        <div class="grid gap-3 md:grid-cols-[1fr_2fr]">
            <Field label="Name"><input bind:value={name} onblur={saveSession} maxlength="200" /></Field>
            <Field label="Notes"><textarea rows="2" bind:value={notes} onblur={saveSession}></textarea></Field>
        </div>
        <div class="mt-3 flex flex-wrap items-center gap-2">
            <Button icon="download" busy={exporting} onclick={exportAll}>Export session (ZIP)</Button>
            <Button onclick={archive}>{store.session?.archived ? 'Unarchive' : 'Archive'}</Button>
            <span class="num ml-2 text-xs text-muted">{fmtCount(store.session?.job_count)} jobs · {fmtCount(store.session?.measurement_count)} points</span>
            <Button variant="danger" class="ml-auto" onclick={deleteSession}>Delete session</Button>
        </div>
    </Panel>

    <div class="grid gap-4 xl:grid-cols-2">
        <Panel title="External sensors" flush>
            {#if sensors.length === 0}
                <p class="px-3 py-4 text-[13px] text-muted">None connected. Sensors (e.g. GNSS receivers) appear when they stream positions to the server.</p>
            {:else}
                <table class="data-table">
                    <thead><tr><th>Name</th><th>IP</th><th class="r">Positions</th><th>Logging</th><th></th></tr></thead>
                    <tbody>
                        {#each sensors as s (s.id)}
                            <tr>
                                <td><input class="!w-40 !py-1" value={s.name} onchange={(e) => updateSensor(s.id, { name: (e.currentTarget as HTMLInputElement).value })} /></td>
                                <td class="num">{s.ip}</td>
                                <td class="r num">{fmtCount(s.count)}</td>
                                <td><input type="checkbox" checked={s.logging_active} aria-label="Logging" onchange={(e) => updateSensor(s.id, { logging_active: (e.currentTarget as HTMLInputElement).checked })} /></td>
                                <td class="r"><Button size="sm" disabled={s.count === 0} onclick={() => download(`/external-sensors/${s.id}/trajectory`, 'sensor.traj').catch((e) => toast.error(e.message))}>.traj</Button></td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            {/if}
        </Panel>

        <Panel title="Time synchronization between two sensors">
            <div class="grid gap-3 sm:grid-cols-2">
                <Field label="First sensor">
                    <select bind:value={roles.primary_sensor_id}><option value={null}>–</option>{#each syncOptions as o (o.id)}<option value={o.id}>{o.label}</option>{/each}</select>
                </Field>
                <Field label="Second sensor">
                    <select bind:value={roles.secondary_sensor_id}><option value={null}>–</option>{#each syncOptions as o (o.id)}<option value={o.id}>{o.label}</option>{/each}</select>
                </Field>
            </div>
            <div class="mt-3 flex flex-wrap items-center gap-2">
                <Button variant="primary" onclick={() => api.setSyncRoles(roles).then((r) => ((roles = r), toast.ok('Applied'))).catch((e) => toast.error(e.message))}>Apply</Button>
                <Button onclick={() => api.resetSync().then(() => toast.ok('Reset')).catch((e) => toast.error(e.message))}>Reset</Button>
                {#if sync}
                    <span class="num ml-auto">Δt {fmtTime(sync.delta_t)} ± {fmtTime(sync.sigma_delta_t)} · bias {sync.bias.toFixed(4)} ± {sync.sigma_bias.toFixed(4)}</span>
                {/if}
            </div>
        </Panel>
    </div>

    <p class="text-center text-xs"><a class="text-muted hover:text-fg" href="#/settings">App settings: appearance, server address, version</a></p>
</div>

<StationEditor bind:open={editorOpen} rts={editing} />

<Modal bind:open={renameOpen} title="Rename Raspberry Pi">
    {#if renaming}
        <Field label="Name" hint="Leave empty to show its hostname."><input bind:value={renaming.name} maxlength="100" /></Field>
    {/if}
    {#snippet footer()}
        <Button onclick={() => (renameOpen = false)}>Cancel</Button>
        <Button variant="primary" onclick={renameDevice}>Save</Button>
    {/snippet}
</Modal>
