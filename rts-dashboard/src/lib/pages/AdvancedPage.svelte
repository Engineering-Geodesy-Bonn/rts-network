<script lang="ts">
    import { onMount } from 'svelte';
    import { api, download } from '../api';
    import Button from '../components/ui/Button.svelte';
    import Field from '../components/ui/Field.svelte';
    import Icon from '../components/ui/Icon.svelte';
    import { clock } from '../clock.svelte';
    import { confirm } from '../confirm.svelte';
    import { events } from '../events.svelte';
    import { fmtAgo, fmtCount, fmtTime } from '../format';
    import { navigate } from '../router.svelte';
    import { store } from '../store.svelte';
    import { toast } from '../toast.svelte';
    import type { ExternalSensor, SensorRoles, SynchronizerState } from '../types';

    // ── session ────────────────────────────────────────────────────────
    let name = $state(store.session?.name ?? '');
    let notes = $state(store.session?.notes ?? '');
    let saving = $state(false);
    let exporting = $state(false);

    async function saveSession() {
        saving = true;
        try {
            store.session = await api.updateSession(store.session!.id, { name: name.trim(), notes });
            toast.ok('Session saved');
        } catch (e) {
            toast.error((e as Error).message);
        } finally {
            saving = false;
        }
    }

    async function toggleArchive() {
        try {
            store.session = await api.updateSession(store.session!.id, { archived: !store.session!.archived });
        } catch (e) {
            toast.error((e as Error).message);
        }
    }

    async function exportSession() {
        exporting = true;
        try {
            toast.ok(`Downloaded ${await download(`/sessions/${store.session!.id}/export`, 'session.zip')}`);
        } catch (e) {
            toast.error((e as Error).message);
        } finally {
            exporting = false;
        }
    }

    async function deleteSession() {
        const s = store.session!;
        const ok = await confirm({
            title: `Delete session “${s.name}”?`,
            message: `All ${s.rts_count} stations, ${fmtCount(s.job_count)} jobs and ${fmtCount(s.measurement_count)} measurements of this session are deleted permanently. Export the session first if you still need the data.`,
            confirm: 'Delete permanently',
            danger: true,
        });
        if (!ok) return;
        try {
            await api.deleteSession(s.id);
            toast.ok('Session deleted');
            navigate('#/');
        } catch (e) {
            toast.error((e as Error).message);
        }
    }

    // ── devices ────────────────────────────────────────────────────────
    async function renameDevice(id: string, value: string) {
        try {
            await api.updateDevice(id, value.trim() || null);
            store.devices = await api.devices();
        } catch (e) {
            toast.error((e as Error).message);
        }
    }

    async function forgetDevice(id: string) {
        const ok = await confirm({
            title: 'Forget this device?',
            message: 'Stations assigned to it lose their device assignment. A running worker registers the device again.',
            confirm: 'Forget',
            danger: true,
        });
        if (!ok) return;
        try {
            await api.deleteDevice(id);
            store.devices = await api.devices();
        } catch (e) {
            toast.error((e as Error).message);
        }
    }

    // ── external sensors & synchronizer ────────────────────────────────
    let sensors = $state<ExternalSensor[]>([]);
    let roles = $state<SensorRoles>({ primary_sensor_id: null, secondary_sensor_id: null });
    let syncState = $state<SynchronizerState | null>(null);

    async function loadSensors() {
        try {
            [sensors, roles] = await Promise.all([api.externalSensors(), api.syncRoles()]);
        } catch {
            /* shown as empty */
        }
    }

    onMount(() => {
        void loadSensors();
        const off = events.on((e) => {
            if (e.type === 'changed' && (e.entity === 'external_sensor' || e.entity === 'synchronizer')) void loadSensors();
        });
        const timer = setInterval(async () => {
            if (roles.primary_sensor_id && roles.secondary_sensor_id) syncState = await api.syncState().catch(() => null);
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

    async function deleteSensor(sensor: ExternalSensor) {
        const ok = await confirm({ title: `Delete ${sensor.name}?`, message: `${fmtCount(sensor.count)} logged measurements are deleted.`, confirm: 'Delete', danger: true });
        if (!ok) return;
        try {
            await api.deleteExternalSensor(sensor.id);
            await loadSensors();
        } catch (e) {
            toast.error((e as Error).message);
        }
    }

    async function setRoles() {
        try {
            roles = await api.setSyncRoles(roles);
            toast.ok('Synchronizer restarted with the new sensors');
        } catch (e) {
            toast.error((e as Error).message);
        }
    }

    let syncOptions = $derived([
        ...store.rts.map((r) => ({ id: r.id, label: `RTS · ${r.name}` })),
        ...sensors.map((s) => ({ id: s.id, label: `Sensor · ${s.name}` })),
    ]);
</script>

<h1 class="mb-4 text-xl font-bold">More</h1>

<div class="grid gap-4 xl:grid-cols-2">
    <section class="rounded-xl border border-line bg-surface p-4 shadow-sm">
        <h2 class="mb-3 font-semibold">Session</h2>
        <div class="space-y-3">
            <Field label="Name"><input bind:value={name} maxlength="200" /></Field>
            <Field label="Notes"><textarea rows="3" bind:value={notes}></textarea></Field>
            <div class="flex flex-wrap gap-2">
                <Button variant="primary" busy={saving} disabled={!name.trim()} onclick={saveSession}>Save</Button>
                <Button icon="download" busy={exporting} onclick={exportSession}>Export all data (ZIP)</Button>
                <Button onclick={toggleArchive}>{store.session?.archived ? 'Unarchive' : 'Archive'}</Button>
                <Button variant="danger" icon="trash" class="ml-auto" onclick={deleteSession}>Delete session</Button>
            </div>
        </div>
    </section>

    <section class="rounded-xl border border-line bg-surface p-4 shadow-sm">
        <h2 class="mb-1 font-semibold">Worker devices</h2>
        <p class="mb-3 text-sm text-muted">Devices register automatically when their worker starts. Give them a name you recognise in the field.</p>
        <ul class="divide-y divide-line">
            {#each store.devices as d (d.id)}
                <li class="flex flex-wrap items-center gap-2 py-2">
                    <Icon name="cpu" class="text-muted" />
                    <input class="!w-48" value={d.name ?? ''} placeholder={d.hostname ?? d.ip} onchange={(e) => renameDevice(d.id, (e.currentTarget as HTMLInputElement).value)} />
                    <span class="text-xs text-muted">{d.hostname ?? '–'} · {d.ip} · seen {fmtAgo(d.last_seen, clock.server)}</span>
                    <Button size="sm" variant="ghost" icon="trash" class="ml-auto" title="Forget device" onclick={() => forgetDevice(d.id)} />
                </li>
            {:else}
                <li class="py-2 text-sm text-muted">No devices yet.</li>
            {/each}
        </ul>
    </section>

    <section class="rounded-xl border border-line bg-surface p-4 shadow-sm">
        <h2 class="mb-1 font-semibold">External sensors</h2>
        <p class="mb-3 text-sm text-muted">Sensors that stream positions to the API (e.g. GNSS receivers). Logging must be enabled to store their data.</p>
        <ul class="divide-y divide-line">
            {#each sensors as s (s.id)}
                <li class="flex flex-wrap items-center gap-2 py-2">
                    <input class="!w-44" value={s.name} onchange={(e) => updateSensor(s.id, { name: (e.currentTarget as HTMLInputElement).value })} />
                    <span class="text-xs text-muted">{s.ip} · {fmtCount(s.count)} pts · seen {fmtAgo(s.last_seen, clock.server)}</span>
                    <label class="ml-auto flex items-center gap-2 text-sm">
                        <input type="checkbox" checked={s.logging_active} onchange={(e) => updateSensor(s.id, { logging_active: (e.currentTarget as HTMLInputElement).checked })} />
                        Logging
                    </label>
                    <Button size="sm" icon="download" title="Download trajectory" disabled={s.count === 0} onclick={() => download(`/external-sensors/${s.id}/trajectory`, 'sensor.traj').catch((e) => toast.error(e.message))} />
                    <Button size="sm" variant="ghost" icon="trash" title="Delete" onclick={() => deleteSensor(s)} />
                </li>
            {:else}
                <li class="py-2 text-sm text-muted">No external sensors have connected.</li>
            {/each}
        </ul>
    </section>

    <section class="rounded-xl border border-line bg-surface p-4 shadow-sm">
        <h2 class="mb-1 font-semibold">Online time synchronization</h2>
        <p class="mb-3 text-sm text-muted">Estimates the time offset between two sensors that observe the same moving target.</p>
        <div class="grid gap-3 sm:grid-cols-2">
            <Field label="Primary sensor">
                <select bind:value={roles.primary_sensor_id}>
                    <option value={null}>–</option>
                    {#each syncOptions as o (o.id)}<option value={o.id}>{o.label}</option>{/each}
                </select>
            </Field>
            <Field label="Secondary sensor">
                <select bind:value={roles.secondary_sensor_id}>
                    <option value={null}>–</option>
                    {#each syncOptions as o (o.id)}<option value={o.id}>{o.label}</option>{/each}
                </select>
            </Field>
        </div>
        <div class="mt-3 flex gap-2">
            <Button variant="primary" onclick={setRoles}>Apply</Button>
            <Button icon="refresh" onclick={() => api.resetSync().then(() => toast.ok('Synchronizer reset'))}>Reset</Button>
        </div>
        {#if syncState}
            <dl class="mt-4 grid grid-cols-2 gap-3 text-sm">
                <div><dt class="text-xs text-muted">Time offset Δt</dt><dd class="text-lg font-semibold tabular">{fmtTime(syncState.delta_t)} <span class="text-xs font-normal text-muted">± {fmtTime(syncState.sigma_delta_t)}</span></dd></div>
                <div><dt class="text-xs text-muted">Bias</dt><dd class="text-lg font-semibold tabular">{syncState.bias.toFixed(4)} <span class="text-xs font-normal text-muted">± {syncState.sigma_bias.toFixed(4)}</span></dd></div>
            </dl>
        {/if}
    </section>
</div>
