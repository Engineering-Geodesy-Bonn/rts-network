<!-- Find a Bluetooth instrument from the chosen Raspberry Pi: remembered instruments and a scan.
     "Use" connects from the Pi, finds the GeoCOM channel and hands the port to the station. -->
<script lang="ts">
    import { onDestroy, onMount } from 'svelte';
    import { api } from '../api';
    import type { BluetoothInstrument, BluetoothRequest, BluetoothSeen } from '../types';
    import Button from './ui/Button.svelte';
    import Tag from './ui/Tag.svelte';

    let { deviceId, currentPort = '', onpick }: { deviceId: string; currentPort?: string; onpick: (instrument: BluetoothInstrument) => void } = $props();

    let known = $state<BluetoothInstrument[]>([]);
    let found = $state<BluetoothSeen[]>([]);
    let scanning = $state(false);
    let scanned = $state(false);
    let connecting = $state<string | null>(null); // address
    let error = $state('');
    let destroyed = false;

    interface Row {
        address: string;
        title: string;
        detail: string;
        rssi: number | null;
        known: BluetoothInstrument | null;
        leica: boolean;
    }

    const LEICA_NAME = /^TS\d+$/;

    let rows = $derived.by((): Row[] => {
        const byAddress = new Map<string, Row>();
        for (const k of known) {
            byAddress.set(k.address, {
                address: k.address,
                title: k.instrument_name ?? k.name ?? k.address,
                detail: [k.serial_number ? `S/N ${k.serial_number}` : '', k.name ?? '', k.address].filter(Boolean).join(' · '),
                rssi: null,
                known: k,
                leica: true,
            });
        }
        for (const f of found) {
            const row = byAddress.get(f.address);
            if (row) row.rssi = f.rssi;
            else
                byAddress.set(f.address, {
                    address: f.address,
                    title: f.name ?? 'Unnamed device',
                    detail: f.address,
                    rssi: f.rssi,
                    known: null,
                    leica: LEICA_NAME.test(f.name ?? ''),
                });
        }
        // Instruments first, then the closest
        return [...byAddress.values()].sort(
            (a, b) => Number(b.leica) - Number(a.leica) || (b.rssi ?? -999) - (a.rssi ?? -999) || a.title.localeCompare(b.title),
        );
    });

    const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

    /** Polls a request until it is finished; onUpdate gets every intermediate state. */
    async function follow(request: BluetoothRequest, onUpdate?: (r: BluetoothRequest) => void): Promise<BluetoothRequest> {
        while (!destroyed && (request.status === 'pending' || request.status === 'running')) {
            await sleep(700);
            request = await api.bluetoothRequest(request.id);
            onUpdate?.(request);
        }
        return request;
    }

    async function loadKnown() {
        try {
            known = await api.bluetoothInstruments();
        } catch {
            /* the list is a convenience */
        }
    }

    async function scan() {
        error = '';
        scanning = true;
        try {
            const result = await follow(await api.bluetoothScan(deviceId), (r) => (found = r.found));
            found = result.found;
            if (result.status === 'failed') error = result.error ?? 'Scan failed';
            scanned = true;
        } catch (e) {
            error = (e as Error).message;
        } finally {
            scanning = false;
        }
    }

    async function use(row: Row) {
        error = '';
        connecting = row.address;
        try {
            const result = await follow(await api.bluetoothIdentify(deviceId, row.address));
            if (result.status === 'done' && result.instrument) {
                await loadKnown();
                onpick(result.instrument);
            } else {
                error = `${row.title}: ${result.error ?? 'connection failed'}`;
            }
        } catch (e) {
            error = `${row.title}: ${(e as Error).message}`;
        } finally {
            connecting = null;
        }
    }

    async function forget(row: Row) {
        try {
            await api.forgetBluetoothInstrument(row.address);
            await loadKnown();
        } catch (e) {
            error = (e as Error).message;
        }
    }

    function signal(rssi: number | null): string {
        if (rssi == null) return '';
        return rssi >= -60 ? 'strong' : rssi >= -75 ? 'medium' : 'weak';
    }

    const inUse = (address: string) => currentPort.toUpperCase().startsWith(`BT://${address}`);

    onMount(() => {
        void loadKnown();
        void scan();
    });
    onDestroy(() => (destroyed = true));
</script>

<div class="rounded border border-line bg-surface-2/50 p-3">
    <div class="mb-2 flex items-center gap-2">
        <span class="label">Bluetooth instruments near this Raspberry Pi</span>
        <Button class="ml-auto" size="sm" icon="refresh" busy={scanning} disabled={scanning || connecting !== null} onclick={scan}>
            {scanning ? 'Searching…' : 'Search again'}
        </Button>
    </div>

    {#if rows.length === 0}
        <p class="py-2 text-sm text-muted">
            {scanning ? 'Searching for instruments (about 10 s)…' : scanned ? 'No Bluetooth device found. Is the instrument on, with GeoCOM set to Bluetooth?' : ''}
        </p>
    {:else}
        <ul class="divide-y divide-line">
            {#each rows as row (row.address)}
                <li class="flex items-center gap-3 py-2">
                    <div class="min-w-0 flex-1">
                        <div class="flex flex-wrap items-center gap-1.5">
                            <span class="truncate font-medium">{row.title}</span>
                            {#if inUse(row.address)}<Tag tone="accent" text="selected" />{/if}
                            {#if row.known}<Tag tone="good" text="known" />{/if}
                            {#if row.rssi != null}<Tag tone={signal(row.rssi) === 'weak' ? 'warn' : 'neutral'} text={`${signal(row.rssi)} signal`} />{:else if scanned && row.known}<Tag text="not seen" />{/if}
                        </div>
                        <div class="truncate text-xs text-muted">{row.detail}</div>
                    </div>
                    {#if row.known && connecting !== row.address}
                        <Button size="sm" variant="quiet" title="Forget this instrument" icon="trash" disabled={connecting !== null} onclick={() => forget(row)} />
                    {/if}
                    <Button size="sm" variant={row.leica ? 'primary' : 'default'} icon="bluetooth" busy={connecting === row.address} disabled={connecting !== null} onclick={() => use(row)}>
                        {connecting === row.address ? 'Connecting…' : 'Use'}
                    </Button>
                </li>
            {/each}
        </ul>
    {/if}

    {#if error}<p class="mt-2 text-sm text-bad">{error}</p>{/if}
    <p class="mt-2 text-xs text-muted">
        On the instrument, set GeoCOM to <em>TS Bluetooth 1</em>. <em>Use</em> connects from the Raspberry Pi, finds the GeoCOM channel and fills in the port.
    </p>
</div>
