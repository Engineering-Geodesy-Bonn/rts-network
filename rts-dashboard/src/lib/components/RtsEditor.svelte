<!-- Create or edit an RTS. Shows field units (gon, mgon, mm, ms); the API stores SI units. -->
<script lang="ts">
    import { api } from '../api';
    import { INTERNAL_DELAYS, units } from '../format';
    import { store } from '../store.svelte';
    import { toast } from '../toast.svelte';
    import type { RTS, RTSConfig } from '../types';
    import Button from './ui/Button.svelte';
    import Field from './ui/Field.svelte';
    import Modal from './ui/Modal.svelte';

    let { open = $bindable(false), rts = null }: { open?: boolean; rts?: RTS | null } = $props();

    interface Form {
        name: string;
        device_id: string;
        port: string;
        baudrate: number;
        timeout: number;
        parity: string;
        stopbits: number;
        bytesize: number;
        station_x: number;
        station_y: number;
        station_z: number;
        orientation_gon: number;
        internal_delay_ms: number;
        external_delay_ms: number;
        distance_std_mm: number;
        angle_std_mgon: number;
        distance_ppm: number;
    }

    function initial(r: RTS | null): Form {
        const deviceId = r?.device_id ?? (store.devices.length === 1 ? store.devices[0].id : '');
        return {
            name: r?.name ?? `RTS ${store.rts.length + 1}`,
            device_id: deviceId ?? '',
            port: r?.port ?? '/dev/ttyUSB0',
            baudrate: r?.baudrate ?? 115200,
            timeout: r?.timeout ?? 30,
            parity: r?.parity ?? 'N',
            stopbits: r?.stopbits ?? 1,
            bytesize: r?.bytesize ?? 8,
            station_x: r?.station_x ?? 0,
            station_y: r?.station_y ?? 0,
            station_z: r?.station_z ?? 0,
            orientation_gon: round(units.radToGon(r?.orientation ?? 0), 6),
            internal_delay_ms: round(units.sToMs(r?.internal_delay ?? 0), 4),
            external_delay_ms: round(units.sToMs(r?.external_delay ?? 0), 4),
            distance_std_mm: round(units.mToMm(r?.distance_std_dev ?? 0.001), 4),
            angle_std_mgon: round(units.radToMgon(r?.angle_std_dev ?? units.mgonToRad(0.3)), 4),
            distance_ppm: r?.distance_ppm ?? 1,
        };
    }

    function round(v: number, digits: number): number {
        return Number(v.toFixed(digits));
    }

    let form = $state<Form>(initial(null));
    let busy = $state(false);
    let advanced = $state(false);

    $effect(() => {
        if (open) {
            form = initial(rts);
            advanced = false;
        }
    });

    // serial ports reported by the workers of the selected device
    let ports = $derived.by(() => {
        const device = store.board?.devices.find((d) => d.device_id === form.device_id);
        const list = new Set<string>();
        for (const w of device?.workers ?? []) {
            for (const p of w.heartbeat.system.serial_ports ?? []) list.add(p.path);
        }
        return [...list];
    });

    function config(): RTSConfig {
        return {
            name: form.name.trim(),
            port: form.port.trim(),
            baudrate: Number(form.baudrate),
            timeout: Number(form.timeout),
            parity: form.parity,
            stopbits: Number(form.stopbits),
            bytesize: Number(form.bytesize),
            station_x: Number(form.station_x),
            station_y: Number(form.station_y),
            station_z: Number(form.station_z),
            orientation: units.gonToRad(Number(form.orientation_gon)),
            internal_delay: units.msToS(Number(form.internal_delay_ms)),
            external_delay: units.msToS(Number(form.external_delay_ms)),
            distance_std_dev: units.mmToM(Number(form.distance_std_mm)),
            angle_std_dev: units.mgonToRad(Number(form.angle_std_mgon)),
            distance_ppm: Number(form.distance_ppm),
        };
    }

    async function save(e?: SubmitEvent) {
        e?.preventDefault();
        busy = true;
        try {
            if (rts) {
                await api.updateRts(rts.id, { ...config(), device_id: form.device_id || null });
                toast.ok(`${form.name} saved`);
            } else {
                await api.createRts({ ...config(), session_id: store.session!.id, device_id: form.device_id || null });
                toast.ok(`${form.name} added`);
            }
            store.rts = await api.rtsList(store.session!.id);
            open = false;
        } catch (err) {
            toast.error((err as Error).message);
        } finally {
            busy = false;
        }
    }
</script>

<Modal bind:open title={rts ? `Edit ${rts.name}` : 'Add total station'} wide>
    <form id="rts-form" class="space-y-6" onsubmit={save}>
        <section>
            <h3 class="mb-3 text-sm font-semibold">Connection</h3>
            <div class="grid gap-3 sm:grid-cols-2">
                <Field label="Name"><input bind:value={form.name} required maxlength="100" /></Field>
                <Field label="Worker device" hint={store.devices.length === 0 ? 'Start a worker: devices register automatically.' : ''}>
                    <select bind:value={form.device_id}>
                        <option value="">– not assigned –</option>
                        {#each store.devices as d (d.id)}
                            <option value={d.id}>{d.name || d.hostname || d.ip}{d.hostname || d.name ? ` (${d.ip})` : ''}</option>
                        {/each}
                    </select>
                </Field>
                <Field label="Serial port" hint="sim://name selects the instrument simulator">
                    <input bind:value={form.port} required list="rts-ports" />
                    <datalist id="rts-ports">
                        {#each ports as p (p)}<option value={p}></option>{/each}
                    </datalist>
                </Field>
                <Field label="Baud rate">
                    <select bind:value={form.baudrate}>
                        {#each [9600, 19200, 38400, 57600, 115200] as b (b)}<option value={b}>{b}</option>{/each}
                    </select>
                </Field>
            </div>
            <button type="button" class="mt-2 text-xs text-accent" onclick={() => (advanced = !advanced)}>
                {advanced ? 'Hide' : 'Show'} serial details
            </button>
            {#if advanced}
                <div class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <Field label="Timeout" unit="s"><input type="number" min="1" bind:value={form.timeout} /></Field>
                    <Field label="Parity">
                        <select bind:value={form.parity}><option value="N">None</option><option value="E">Even</option><option value="O">Odd</option></select>
                    </Field>
                    <Field label="Stop bits"><select bind:value={form.stopbits}><option value={1}>1</option><option value={2}>2</option></select></Field>
                    <Field label="Byte size"><select bind:value={form.bytesize}>{#each [5, 6, 7, 8] as b (b)}<option value={b}>{b}</option>{/each}</select></Field>
                </div>
            {/if}
        </section>

        <section>
            <h3 class="mb-3 text-sm font-semibold">Station setup</h3>
            <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Field label="Easting" unit="m"><input type="number" step="any" bind:value={form.station_x} /></Field>
                <Field label="Northing" unit="m"><input type="number" step="any" bind:value={form.station_y} /></Field>
                <Field label="Height" unit="m"><input type="number" step="any" bind:value={form.station_z} /></Field>
                <Field label="Orientation" unit="gon"><input type="number" step="any" bind:value={form.orientation_gon} /></Field>
            </div>
        </section>

        <section>
            <h3 class="mb-3 text-sm font-semibold">Timing</h3>
            <div class="grid gap-3 sm:grid-cols-3">
                <Field label="Instrument model" hint="Sets the intrinsic delay">
                    <select onchange={(e) => {
                        const v = (e.currentTarget as HTMLSelectElement).value;
                        if (v in INTERNAL_DELAYS) form.internal_delay_ms = round(INTERNAL_DELAYS[v] * 1000, 4);
                    }}>
                        <option value="">Custom</option>
                        {#each Object.entries(INTERNAL_DELAYS) as [model, delay] (model)}
                            <option value={model} selected={Math.abs(delay * 1000 - form.internal_delay_ms) < 1e-6}>{model} ({(delay * 1000).toFixed(2)} ms)</option>
                        {/each}
                    </select>
                </Field>
                <Field label="Intrinsic delay" unit="ms"><input type="number" step="any" bind:value={form.internal_delay_ms} /></Field>
                <Field label="External delay" unit="ms"><input type="number" step="any" bind:value={form.external_delay_ms} /></Field>
            </div>
        </section>

        <section>
            <h3 class="mb-3 text-sm font-semibold">Accuracy</h3>
            <div class="grid grid-cols-3 gap-3">
                <Field label="Distance σ" unit="mm"><input type="number" step="any" min="0" bind:value={form.distance_std_mm} /></Field>
                <Field label="Distance" unit="ppm"><input type="number" step="any" min="0" bind:value={form.distance_ppm} /></Field>
                <Field label="Angle σ" unit="mgon"><input type="number" step="any" min="0" bind:value={form.angle_std_mgon} /></Field>
            </div>
        </section>
    </form>
    {#snippet footer()}
        <Button onclick={() => (open = false)}>Cancel</Button>
        <Button variant="primary" {busy} onclick={() => (document.getElementById('rts-form') as HTMLFormElement).requestSubmit()}>
            {rts ? 'Save' : 'Add'}
        </Button>
    {/snippet}
</Modal>
