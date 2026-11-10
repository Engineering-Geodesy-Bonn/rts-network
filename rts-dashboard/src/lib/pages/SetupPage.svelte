<script lang="ts">
    import { onMount } from 'svelte';
    import { api, download } from '../api';
    import StationEditor from '../components/StationEditor.svelte';
    import Button from '../components/ui/Button.svelte';
    import Field from '../components/ui/Field.svelte';
    import Modal from '../components/ui/Modal.svelte';
    import { confirm } from '../confirm.svelte';
    import { events } from '../events.svelte';
    import { fmtBytes, fmtCount, fmtDuration, fmtTime, rtsColor, units } from '../format';
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

    function deviceStatus(h: DeviceHealth | undefined): { text: string; tone: string } {
        if (!h) return { text: 'Not in use', tone: 'text-muted' };
        if (!h.online) return { text: `Offline${h.last_seen_age != null ? ` for ${fmtDuration(h.last_seen_age)}` : ''}`, tone: 'text-bad' };
        if (h.time_sync === 'gnss') return { text: `Online · GNSS time (±${fmtTime(h.time_error)})`, tone: 'text-good' };
        if (h.time_sync === 'network') return { text: 'Online · network time only', tone: 'text-warn' };
        if (h.time_sync === 'none') return { text: 'Online · clock not synchronized', tone: 'text-bad' };
        return { text: 'Online · time sync unknown', tone: 'text-warn' };
    }

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
        store.session = await api.updateSession(store.session!.id, { archived: !store.session!.archived });
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

<div class="space-y-10">
    <!-- Stations -->
    <section>
        <div class="mb-3 flex items-center gap-3">
            <h1 class="mr-auto text-xl font-semibold">Total stations</h1>
            <Button variant="primary" icon="plus" onclick={() => edit(null)}>Add</Button>
        </div>
        {#if store.rts.length === 0}
            <p class="card px-5 py-8 text-center text-muted">No total stations yet. Add one for every instrument you set up.</p>
        {:else}
            <ul class="card">
                {#each store.rts as rts, index (rts.id)}
                    <li class="border-b border-line last:border-b-0">
                        <button class="flex w-full flex-wrap items-center gap-x-6 gap-y-1 px-5 py-4 text-left hover:bg-surface-2" onclick={() => edit(rts)}>
                            <span class="flex min-w-44 flex-1 items-center gap-3">
                                <span class="h-9 w-1.5 shrink-0 rounded-full" style="background: {rtsColor(index)}"></span>
                                <span>
                                    <span class="block text-[17px] font-semibold">{rts.name}</span>
                                    <span class="block text-sm {rts.device_id ? 'text-muted' : 'text-bad'}">{rts.device_id ? `${store.deviceLabel(rts.device_id)} · ${rts.port}` : 'No Raspberry Pi assigned'}</span>
                                </span>
                            </span>
                            <span class="num text-sm text-muted">
                                E {rts.station_x.toFixed(3)} · N {rts.station_y.toFixed(3)} · H {rts.station_z.toFixed(3)} · {units.radToGon(rts.orientation).toFixed(4)} gon
                            </span>
                            <span class="text-sm text-accent">Edit</span>
                        </button>
                    </li>
                {/each}
            </ul>
        {/if}
    </section>

    <!-- Devices -->
    <section>
        <h2 class="mb-1 text-xl font-semibold">Raspberry Pis</h2>
        <p class="mb-3 text-muted">They appear here automatically when their worker starts.</p>
        {#if relevantDevices.length === 0}
            <p class="card px-5 py-8 text-center text-muted">No Raspberry Pi is connected.</p>
        {:else}
            <ul class="card">
                {#each relevantDevices as d (d.id)}
                    {@const h = deviceHealth.get(d.id)}
                    {@const status = deviceStatus(h)}
                    <li class="flex flex-wrap items-center gap-x-6 gap-y-1 border-b border-line px-5 py-4 last:border-b-0">
                        <span class="min-w-44 flex-1">
                            <span class="block font-semibold">{d.name || d.hostname || d.ip}</span>
                            <span class="block text-sm {status.tone}">{status.text}</span>
                        </span>
                        <span class="num text-sm text-muted">
                            {[
                                d.name || d.hostname ? d.ip : null,
                                h?.online && h.cpu_temperature != null ? `${h.cpu_temperature.toFixed(0)} °C` : null,
                                h?.online && h.disk_free != null ? `${fmtBytes(h.disk_free)} free` : null,
                                h?.unsent ? `${fmtCount(h.unsent)} measurements to upload` : null,
                            ]
                                .filter(Boolean)
                                .join(' · ')}
                        </span>
                        <Button variant="quiet" size="sm" onclick={() => ((renaming = { id: d.id, name: d.name ?? '' }), (renameOpen = true))}>Rename</Button>
                    </li>
                {/each}
            </ul>
        {/if}
        {#if otherDevices.length}
            <button class="mt-3 text-sm text-muted hover:text-fg" onclick={() => (showOther = !showOther)}>
                {showOther ? 'Hide' : 'Show'} {otherDevices.length} other Raspberry Pi{otherDevices.length === 1 ? '' : 's'} (offline, not used here)
            </button>
            {#if showOther}
                <ul class="card mt-2">
                    {#each otherDevices as d (d.id)}
                        <li class="flex items-center gap-4 border-b border-line px-5 py-3 last:border-b-0">
                            <span class="flex-1">{d.name || d.hostname || d.ip}{#if d.name || d.hostname}<span class="text-muted"> · {d.ip}</span>{/if}</span>
                            <Button variant="quiet" size="sm" onclick={() => forgetDevice(d.id)}>Forget</Button>
                        </li>
                    {/each}
                </ul>
            {/if}
        {/if}
    </section>

    <!-- Session -->
    <section>
        <h2 class="mb-3 text-xl font-semibold">Session</h2>
        <div class="card space-y-4 p-5">
            <Field label="Name"><input bind:value={name} onblur={saveSession} maxlength="200" /></Field>
            <Field label="Notes"><textarea rows="3" bind:value={notes} onblur={saveSession}></textarea></Field>
            <div class="flex flex-wrap gap-2 pt-1">
                <Button icon="download" busy={exporting} onclick={exportAll}>Download all data</Button>
                <Button onclick={archive}>{store.session?.archived ? 'Unarchive' : 'Archive'}</Button>
                <Button variant="danger" class="ml-auto" onclick={deleteSession}>Delete session</Button>
            </div>
        </div>
    </section>

    <!-- Rarely used -->
    <details class="group">
        <summary class="cursor-pointer text-xl font-semibold text-muted group-open:text-fg">External sensors and time synchronization</summary>
        <div class="mt-4 space-y-6">
            <div class="card p-5">
                <h3 class="font-semibold">External sensors</h3>
                <p class="mb-3 text-sm text-muted">Devices that stream positions to the server, e.g. a GNSS receiver. Data is only stored while logging is on.</p>
                {#each sensors as s (s.id)}
                    <div class="flex flex-wrap items-center gap-3 border-t border-line py-3">
                        <input class="!w-48" value={s.name} onchange={(e) => updateSensor(s.id, { name: (e.currentTarget as HTMLInputElement).value })} />
                        <span class="text-sm text-muted">{s.ip} · {fmtCount(s.count)} positions</span>
                        <label class="ml-auto flex items-center gap-2"><input type="checkbox" checked={s.logging_active} onchange={(e) => updateSensor(s.id, { logging_active: (e.currentTarget as HTMLInputElement).checked })} /> Logging</label>
                        <Button size="sm" disabled={s.count === 0} onclick={() => download(`/external-sensors/${s.id}/trajectory`, 'sensor.traj').catch((e) => toast.error(e.message))}>Download</Button>
                    </div>
                {:else}
                    <p class="text-sm text-muted">None connected.</p>
                {/each}
            </div>
            <div class="card p-5">
                <h3 class="font-semibold">Time synchronization between two sensors</h3>
                <p class="mb-3 text-sm text-muted">Estimates the time offset between two sensors that follow the same target.</p>
                <div class="grid gap-4 sm:grid-cols-2">
                    <Field label="First sensor">
                        <select bind:value={roles.primary_sensor_id}><option value={null}>–</option>{#each syncOptions as o (o.id)}<option value={o.id}>{o.label}</option>{/each}</select>
                    </Field>
                    <Field label="Second sensor">
                        <select bind:value={roles.secondary_sensor_id}><option value={null}>–</option>{#each syncOptions as o (o.id)}<option value={o.id}>{o.label}</option>{/each}</select>
                    </Field>
                </div>
                <div class="mt-4 flex flex-wrap items-center gap-2">
                    <Button variant="primary" onclick={() => api.setSyncRoles(roles).then((r) => ((roles = r), toast.ok('Applied'))).catch((e) => toast.error(e.message))}>Apply</Button>
                    <Button onclick={() => api.resetSync().then(() => toast.ok('Reset'))}>Reset</Button>
                    {#if sync}
                        <span class="num ml-auto">Offset <b>{fmtTime(sync.delta_t)}</b> <span class="text-muted">± {fmtTime(sync.sigma_delta_t)}</span></span>
                    {/if}
                </div>
            </div>
        </div>
    </details>

    <p class="text-center"><a class="text-muted hover:text-fg" href="#/settings">App settings (appearance, server address)</a></p>
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
