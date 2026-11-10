<!-- Add or edit a total station. Field units (gon, mgon, mm, ms); the API stores SI units. -->
<script lang="ts">
    import { api } from '../api';
    import { confirm } from '../confirm.svelte';
    import { EDM_MEASUREMENT_MODES, FINE_ADJUST_POSITION_MODES, INTERNAL_DELAYS, PRISM_TYPES, TMC_INCLINATION_MODES, TMC_MEASUREMENT_MODES, units } from '../format';
    import { store } from '../store.svelte';
    import { toast } from '../toast.svelte';
    import type { RTS, TrackingSettings } from '../types';
    import Button from './ui/Button.svelte';
    import Field from './ui/Field.svelte';
    import Modal from './ui/Modal.svelte';

    let { open = $bindable(false), rts = null }: { open?: boolean; rts?: RTS | null } = $props();

    const DEFAULT_TRACKING: TrackingSettings = {
        tmc_measurement_mode: 1,
        tmc_inclination_mode: 1,
        edm_measurement_mode: 9,
        prism_type: 3,
        fine_adjust_position_mode: 1,
        fine_adjust_horizontal_search_range: 0.0872,
        fine_adjust_vertical_search_range: 0.0872,
        power_search_area_dcenterhz: 0,
        power_search_area_dcenterv: 1.5708,
        power_search_area_drangehz: 6.283,
        power_search_area_drangev: 0.6,
        power_search_area_enabled: 1,
        power_search_min_range: 1,
        power_search_max_range: 50,
        power_search: true,
    };
    const ANGLES = [
        'fine_adjust_horizontal_search_range',
        'fine_adjust_vertical_search_range',
        'power_search_area_dcenterhz',
        'power_search_area_dcenterv',
        'power_search_area_drangehz',
        'power_search_area_drangev',
    ] as const;

    const r4 = (v: number) => Number(v.toFixed(4));

    function initial(r: RTS | null) {
        const tracking: Record<string, number | boolean> = { ...(r?.tracking ?? DEFAULT_TRACKING) };
        for (const key of ANGLES) tracking[key] = r4(units.radToGon(tracking[key] as number));
        return {
            name: r?.name ?? `Station ${store.rts.length + 1}`,
            device_id: r?.device_id ?? (store.devices.length === 1 ? store.devices[0].id : ''),
            port: r?.port ?? '/dev/ttyUSB0',
            baudrate: r?.baudrate ?? 115200,
            timeout: r?.timeout ?? 30,
            parity: r?.parity ?? 'N',
            stopbits: r?.stopbits ?? 1,
            bytesize: r?.bytesize ?? 8,
            station_x: r?.station_x ?? 0,
            station_y: r?.station_y ?? 0,
            station_z: r?.station_z ?? 0,
            orientation: r4(units.radToGon(r?.orientation ?? 0)),
            internal_delay: r4(units.sToMs(r?.internal_delay ?? 0)),
            external_delay: r4(units.sToMs(r?.external_delay ?? 0)),
            distance_std: r4(units.mToMm(r?.distance_std_dev ?? 0.001)),
            distance_ppm: r?.distance_ppm ?? 1,
            angle_std: r4(units.radToMgon(r?.angle_std_dev ?? units.mgonToRad(0.3))),
            tracking,
        };
    }

    let form = $state(initial(null));
    let busy = $state(false);

    $effect(() => {
        if (open) form = initial(rts);
    });

    let model = $derived(Object.entries(INTERNAL_DELAYS).find(([, d]) => Math.abs(d * 1000 - Number(form.internal_delay)) < 1e-6)?.[0] ?? '');

    const ports = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2', '/dev/ttyUSB3', 'sim://simulator'];

    async function save() {
        busy = true;
        const tracking = { ...form.tracking } as Record<string, number | boolean>;
        for (const key of ANGLES) tracking[key] = units.gonToRad(Number(tracking[key]));
        for (const [key, value] of Object.entries(DEFAULT_TRACKING)) {
            if (typeof value === 'number') tracking[key] = Number(tracking[key]);
        }
        const data = {
            name: form.name.trim(),
            device_id: form.device_id || null,
            port: form.port.trim(),
            baudrate: Number(form.baudrate),
            timeout: Number(form.timeout),
            parity: form.parity,
            stopbits: Number(form.stopbits),
            bytesize: Number(form.bytesize),
            station_x: Number(form.station_x),
            station_y: Number(form.station_y),
            station_z: Number(form.station_z),
            orientation: units.gonToRad(Number(form.orientation)),
            internal_delay: units.msToS(Number(form.internal_delay)),
            external_delay: units.msToS(Number(form.external_delay)),
            distance_std_dev: units.mmToM(Number(form.distance_std)),
            distance_ppm: Number(form.distance_ppm),
            angle_std_dev: units.mgonToRad(Number(form.angle_std)),
            tracking: tracking as unknown as TrackingSettings,
        };
        try {
            if (rts) await api.updateRts(rts.id, data);
            else await api.createRts({ ...data, session_id: store.session!.id });
            store.rts = await api.rtsList(store.session!.id);
            toast.ok(`${data.name} saved`);
            open = false;
        } catch (e) {
            toast.error((e as Error).message);
        } finally {
            busy = false;
        }
    }

    async function remove() {
        if (!rts) return;
        const ok = await confirm({
            title: `Remove ${rts.name}?`,
            message: 'The station is removed from this session. Its measurements stay available under Data.',
            confirm: 'Remove',
            danger: true,
        });
        if (!ok) return;
        try {
            await api.deleteRts(rts.id);
            store.rts = await api.rtsList(store.session!.id);
            open = false;
        } catch (e) {
            toast.error((e as Error).message);
        }
    }
</script>

<Modal bind:open title={rts ? `Edit ${rts.name}` : 'Add total station'} wide>
    <div class="space-y-7">
        <section class="grid gap-4 sm:grid-cols-2">
            <Field label="Name"><input bind:value={form.name} maxlength="100" /></Field>
            <Field label="Raspberry Pi" hint={store.devices.length === 0 ? 'Start the worker on the Pi; it appears here automatically.' : ''}>
                <select bind:value={form.device_id}>
                    <option value="">Choose…</option>
                    {#each store.devices as d (d.id)}<option value={d.id}>{d.name || d.hostname || d.ip}</option>{/each}
                </select>
            </Field>
            <Field label="Serial port" hint="Use sim://name to simulate an instrument.">
                <input bind:value={form.port} list="station-ports" />
                <datalist id="station-ports">{#each ports as p (p)}<option value={p}></option>{/each}</datalist>
            </Field>
            <Field label="Baud rate">
                <select bind:value={form.baudrate}>{#each [9600, 19200, 38400, 57600, 115200] as b (b)}<option value={b}>{b}</option>{/each}</select>
            </Field>
        </section>

        <section>
            <h3 class="mb-3 font-semibold">Station position</h3>
            <div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <Field label="Easting" unit="m"><input type="number" step="any" bind:value={form.station_x} /></Field>
                <Field label="Northing" unit="m"><input type="number" step="any" bind:value={form.station_y} /></Field>
                <Field label="Height" unit="m"><input type="number" step="any" bind:value={form.station_z} /></Field>
                <Field label="Orientation" unit="gon"><input type="number" step="any" bind:value={form.orientation} /></Field>
            </div>
        </section>

        <section>
            <h3 class="mb-3 font-semibold">Timing</h3>
            <div class="grid gap-4 sm:grid-cols-3">
                <Field label="Instrument model">
                    <select value={model} onchange={(e) => {
                        const v = (e.currentTarget as HTMLSelectElement).value;
                        if (v in INTERNAL_DELAYS) form.internal_delay = r4(INTERNAL_DELAYS[v] * 1000);
                    }}>
                        <option value="">Other</option>
                        {#each Object.keys(INTERNAL_DELAYS) as m (m)}<option value={m}>{m}</option>{/each}
                    </select>
                </Field>
                <Field label="Instrument delay" unit="ms"><input type="number" step="any" bind:value={form.internal_delay} /></Field>
                <Field label="External delay" unit="ms"><input type="number" step="any" bind:value={form.external_delay} /></Field>
            </div>
        </section>

        <details class="group">
            <summary class="cursor-pointer font-semibold text-muted group-open:text-fg">Tracking settings</summary>
            <div class="mt-4 grid gap-4 sm:grid-cols-2">
                <Field label="Prism"><select bind:value={form.tracking.prism_type}>{#each Object.entries(PRISM_TYPES) as [v, l] (v)}<option value={Number(v)}>{l}</option>{/each}</select></Field>
                <Field label="Distance mode"><select bind:value={form.tracking.edm_measurement_mode}>{#each Object.entries(EDM_MEASUREMENT_MODES) as [v, l] (v)}<option value={Number(v)}>{l}</option>{/each}</select></Field>
                <Field label="Measurement mode"><select bind:value={form.tracking.tmc_measurement_mode}>{#each Object.entries(TMC_MEASUREMENT_MODES) as [v, l] (v)}<option value={Number(v)}>{l}</option>{/each}</select></Field>
                <Field label="Inclination"><select bind:value={form.tracking.tmc_inclination_mode}>{#each Object.entries(TMC_INCLINATION_MODES) as [v, l] (v)}<option value={Number(v)}>{l}</option>{/each}</select></Field>
                <Field label="Fine adjust mode"><select bind:value={form.tracking.fine_adjust_position_mode}>{#each Object.entries(FINE_ADJUST_POSITION_MODES) as [v, l] (v)}<option value={Number(v)}>{l}</option>{/each}</select></Field>
                <div class="grid grid-cols-2 gap-4">
                    <Field label="Search Hz" unit="gon"><input type="number" step="any" bind:value={form.tracking.fine_adjust_horizontal_search_range} /></Field>
                    <Field label="Search V" unit="gon"><input type="number" step="any" bind:value={form.tracking.fine_adjust_vertical_search_range} /></Field>
                </div>
                <label class="flex items-center gap-2 sm:col-span-2"><input type="checkbox" bind:checked={form.tracking.power_search as boolean} /> Power search when the prism is lost</label>
                {#if form.tracking.power_search}
                    <div class="grid grid-cols-2 gap-4 sm:col-span-2 sm:grid-cols-4">
                        <Field label="Min range" unit="m"><input type="number" bind:value={form.tracking.power_search_min_range} /></Field>
                        <Field label="Max range" unit="m"><input type="number" bind:value={form.tracking.power_search_max_range} /></Field>
                        <Field label="Area center Hz" unit="gon"><input type="number" step="any" bind:value={form.tracking.power_search_area_dcenterhz} /></Field>
                        <Field label="Area center V" unit="gon"><input type="number" step="any" bind:value={form.tracking.power_search_area_dcenterv} /></Field>
                        <Field label="Area width Hz" unit="gon"><input type="number" step="any" bind:value={form.tracking.power_search_area_drangehz} /></Field>
                        <Field label="Area height V" unit="gon"><input type="number" step="any" bind:value={form.tracking.power_search_area_drangev} /></Field>
                        <Field label="Restrict area"><select bind:value={form.tracking.power_search_area_enabled}><option value={1}>Yes</option><option value={0}>No</option></select></Field>
                    </div>
                {/if}
            </div>
        </details>

        <details class="group">
            <summary class="cursor-pointer font-semibold text-muted group-open:text-fg">Accuracy and serial details</summary>
            <div class="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
                <Field label="Distance σ" unit="mm"><input type="number" step="any" bind:value={form.distance_std} /></Field>
                <Field label="Distance" unit="ppm"><input type="number" step="any" bind:value={form.distance_ppm} /></Field>
                <Field label="Angle σ" unit="mgon"><input type="number" step="any" bind:value={form.angle_std} /></Field>
                <Field label="Timeout" unit="s"><input type="number" bind:value={form.timeout} /></Field>
                <Field label="Parity"><select bind:value={form.parity}><option value="N">None</option><option value="E">Even</option><option value="O">Odd</option></select></Field>
                <Field label="Stop bits / byte size">
                    <div class="flex gap-2">
                        <select bind:value={form.stopbits}><option value={1}>1</option><option value={2}>2</option></select>
                        <select bind:value={form.bytesize}>{#each [5, 6, 7, 8] as b (b)}<option value={b}>{b}</option>{/each}</select>
                    </div>
                </Field>
            </div>
        </details>
    </div>

    {#snippet footer()}
        {#if rts}<Button variant="danger" class="mr-auto" onclick={remove}>Remove station</Button>{/if}
        <Button onclick={() => (open = false)}>Cancel</Button>
        <Button variant="primary" {busy} disabled={!form.name.trim() || !form.port.trim()} onclick={save}>Save</Button>
    {/snippet}
</Modal>
