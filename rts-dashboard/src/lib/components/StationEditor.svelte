<!-- Add or edit a total station. Field units (gon, mgon, mm, ms); the API stores SI units. -->
<script lang="ts">
    import { api } from '../api';
    import { confirm } from '../confirm.svelte';
    import { INTERNAL_DELAYS, units } from '../format';
    import { store } from '../store.svelte';
    import { toast } from '../toast.svelte';
    import { trackingFromForm, trackingToForm } from '../tracking';
    import type { BluetoothInstrument, RTS } from '../types';
    import BluetoothPicker from './BluetoothPicker.svelte';
    import TrackingFields from './TrackingFields.svelte';
    import Button from './ui/Button.svelte';
    import Field from './ui/Field.svelte';
    import Modal from './ui/Modal.svelte';

    let { open = $bindable(false), rts = null }: { open?: boolean; rts?: RTS | null } = $props();

    const r4 = (v: number) => Number(v.toFixed(4));

    function initial(r: RTS | null) {
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
            tracking: trackingToForm(r?.tracking),
        };
    }

    let form = $state(initial(null));
    let busy = $state(false);
    let bluetooth = $state(false);

    $effect(() => {
        if (open) {
            form = initial(rts);
            bluetooth = false;
        }
    });

    /** Port, instrument delay and (for a new station with the default name) the name from the instrument. */
    function pickBluetooth(instrument: BluetoothInstrument) {
        form.port = `bt://${instrument.address}/${instrument.channel}`;
        const model = Object.keys(INTERNAL_DELAYS).find((m) => instrument.instrument_name?.startsWith(m));
        if (model) form.internal_delay = r4(INTERNAL_DELAYS[model] * 1000);
        if (!rts && /^Station \d+$/.test(form.name) && model) {
            form.name = instrument.serial_number ? `${model} ${instrument.serial_number}` : model;
        }
        bluetooth = false;
        toast.ok(`${instrument.instrument_name ?? instrument.address} connected on channel ${instrument.channel}`);
    }

    let model = $derived(Object.entries(INTERNAL_DELAYS).find(([, d]) => Math.abs(d * 1000 - Number(form.internal_delay)) < 1e-6)?.[0] ?? '');

    const ports = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2', '/dev/ttyUSB3', 'sim://simulator'];

    async function save() {
        busy = true;
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
            tracking: trackingFromForm(form.tracking),
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
    <div class="space-y-5">
        <section class="grid gap-3 sm:grid-cols-2">
            <Field label="Name"><input bind:value={form.name} maxlength="100" /></Field>
            <Field label="Raspberry Pi" hint={store.devices.length === 0 ? 'Start the worker on the Pi; it appears here automatically.' : ''}>
                <select bind:value={form.device_id}>
                    <option value="">Choose…</option>
                    {#each store.devices as d (d.id)}<option value={d.id}>{d.name || d.hostname || d.ip}</option>{/each}
                </select>
            </Field>
            <Field label="Port" hint="Serial port, bt://address/channel for Bluetooth, or sim://name to simulate an instrument.">
                <div class="flex gap-2">
                    <input class="min-w-0 flex-1" bind:value={form.port} list="station-ports" />
                    <Button icon="bluetooth" disabled={!form.device_id} title={form.device_id ? 'Find a Bluetooth instrument near this Raspberry Pi' : 'Choose the Raspberry Pi first'}
                        onclick={(e) => { e.preventDefault(); bluetooth = !bluetooth; }}>Bluetooth</Button>
                </div>
                <datalist id="station-ports">{#each ports as p (p)}<option value={p}></option>{/each}</datalist>
            </Field>
            {#if !form.port.startsWith('bt://')}
                <Field label="Baud rate">
                    <select bind:value={form.baudrate}>{#each [9600, 19200, 38400, 57600, 115200] as b (b)}<option value={b}>{b}</option>{/each}</select>
                </Field>
            {/if}
            {#if bluetooth && form.device_id}
                {#key form.device_id}
                    <div class="sm:col-span-2"><BluetoothPicker deviceId={form.device_id} currentPort={form.port} onpick={pickBluetooth} /></div>
                {/key}
            {/if}
        </section>

        <section>
            <h3 class="label mb-2 border-b border-line pb-1">Station position</h3>
            <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Field label="Easting" unit="m"><input type="number" step="any" bind:value={form.station_x} /></Field>
                <Field label="Northing" unit="m"><input type="number" step="any" bind:value={form.station_y} /></Field>
                <Field label="Height" unit="m"><input type="number" step="any" bind:value={form.station_z} /></Field>
                <Field label="Orientation" unit="gon"><input type="number" step="any" bind:value={form.orientation} /></Field>
            </div>
        </section>

        <section>
            <h3 class="label mb-2 border-b border-line pb-1">Timing</h3>
            <div class="grid gap-3 sm:grid-cols-3">
                <Field label="Instrument model">
                    <select value={model} onchange={(e) => {
                        const v = (e.currentTarget as HTMLSelectElement).value;
                        if (v in INTERNAL_DELAYS) form.internal_delay = r4(INTERNAL_DELAYS[v] * 1000);
                    }}>
                        <option value="">Other</option>
                        {#each Object.keys(INTERNAL_DELAYS) as m (m)}<option value={m}>{m}</option>{/each}
                    </select>
                </Field>
                <Field label="Instrument delay" unit="ms" hint="Can be estimated on the page of a measurement with a prism on a circle."><input type="number" step="any" bind:value={form.internal_delay} /></Field>
                <Field label="External delay" unit="ms"><input type="number" step="any" bind:value={form.external_delay} /></Field>
            </div>
        </section>

        <details class="group">
            <summary class="label cursor-pointer border-b border-line pb-1 group-open:!text-fg">Tracking settings</summary>
            <div class="mt-3"><TrackingFields bind:tracking={form.tracking} /></div>
        </details>

        <details class="group">
            <summary class="label cursor-pointer border-b border-line pb-1 group-open:!text-fg">Accuracy and serial details</summary>
            <div class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
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
