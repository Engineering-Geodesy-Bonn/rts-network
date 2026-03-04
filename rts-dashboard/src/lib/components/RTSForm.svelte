<script lang="ts">
    import { createRts } from "../api/client";
    import type { DeviceResponse } from "../api/types";

    let {
        devices,
        sessionId,
        onclose,
        onsaved,
    }: {
        devices: DeviceResponse[];
        sessionId: number;
        onclose: () => void;
        onsaved: () => void;
    } = $props();

    let name = $state("RTS");
    // svelte-ignore state_referenced_locally
    const initialDeviceId = devices.length > 0 ? devices[0].id : 0;
    let deviceId = $state(initialDeviceId);
    let port = $state("/dev/ttyUSB0");
    let baudrate = $state(115200);
    let timeout = $state(30);
    let stationX = $state(0);
    let stationY = $state(0);
    let stationZ = $state(0);
    let saving = $state(false);
    let error = $state("");

    async function handleSubmit() {
        saving = true;
        error = "";
        try {
            await createRts({
                name,
                device_id: deviceId,
                session_id: sessionId,
                port,
                baudrate,
                timeout,
                station_x: stationX,
                station_y: stationY,
                station_z: stationZ,
            });
            onsaved();
        } catch (e: any) {
            error = e.message || "Failed to create RTS";
        } finally {
            saving = false;
        }
    }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
    class="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
    onclick={onclose}
    onkeydown={(e) => e.key === "Escape" && onclose()}
    role="dialog"
    tabindex="-1"
>
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
        class="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-md shadow-2xl"
        onclick={(e) => e.stopPropagation()}
        onkeydown={() => {}}
    >
        <div
            class="p-6 border-b border-slate-700 flex items-center justify-between"
        >
            <h2 class="text-xl font-semibold">Add RTS Station</h2>
            <button
                class="text-slate-400 hover:text-white p-1 cursor-pointer"
                onclick={onclose}
                aria-label="Close"
            >
                <svg
                    class="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                >
                    <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M6 18L18 6M6 6l12 12"
                    />
                </svg>
            </button>
        </div>

        <form
            class="p-6 space-y-4"
            onsubmit={(e) => {
                e.preventDefault();
                handleSubmit();
            }}
        >
            {#if error}
                <div
                    class="bg-red-500/10 border border-red-500/30 text-red-400 px-3 py-2 rounded-lg text-sm"
                >
                    {error}
                </div>
            {/if}

            <div>
                <label
                    class="block text-sm font-medium text-slate-300 mb-1"
                    for="rts-name">Name</label
                >
                <input
                    id="rts-name"
                    type="text"
                    bind:value={name}
                    class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors"
                />
            </div>

            <div>
                <label
                    class="block text-sm font-medium text-slate-300 mb-1"
                    for="rts-device">Device</label
                >
                <select
                    id="rts-device"
                    bind:value={deviceId}
                    class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors"
                >
                    {#each devices as dev (dev.id)}
                        <option value={dev.id}>{dev.ip} (ID: {dev.id})</option>
                    {/each}
                    {#if devices.length === 0}
                        <option value={0} disabled>No devices available</option>
                    {/if}
                </select>
            </div>

            <div>
                <label
                    class="block text-sm font-medium text-slate-300 mb-1"
                    for="rts-port">Port</label
                >
                <input
                    id="rts-port"
                    type="text"
                    bind:value={port}
                    class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white font-mono text-sm focus:outline-none focus:border-blue-500 transition-colors"
                />
            </div>

            <div class="grid grid-cols-2 gap-4">
                <div>
                    <label
                        class="block text-sm font-medium text-slate-300 mb-1"
                        for="rts-baudrate">Baudrate</label
                    >
                    <input
                        id="rts-baudrate"
                        type="number"
                        bind:value={baudrate}
                        class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors"
                    />
                </div>
                <div>
                    <label
                        class="block text-sm font-medium text-slate-300 mb-1"
                        for="rts-timeout">Timeout (s)</label
                    >
                    <input
                        id="rts-timeout"
                        type="number"
                        bind:value={timeout}
                        class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors"
                    />
                </div>
            </div>

            <div>
                <span class="block text-sm font-medium text-slate-300 mb-2"
                    >Station Position</span
                >
                <div class="grid grid-cols-3 gap-3">
                    <div>
                        <label
                            class="block text-xs text-slate-500 mb-1"
                            for="rts-sx">X</label
                        >
                        <input
                            id="rts-sx"
                            type="number"
                            step="any"
                            bind:value={stationX}
                            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                        />
                    </div>
                    <div>
                        <label
                            class="block text-xs text-slate-500 mb-1"
                            for="rts-sy">Y</label
                        >
                        <input
                            id="rts-sy"
                            type="number"
                            step="any"
                            bind:value={stationY}
                            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                        />
                    </div>
                    <div>
                        <label
                            class="block text-xs text-slate-500 mb-1"
                            for="rts-sz">Z</label
                        >
                        <input
                            id="rts-sz"
                            type="number"
                            step="any"
                            bind:value={stationZ}
                            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                        />
                    </div>
                </div>
            </div>

            <div class="flex justify-end gap-3 pt-2">
                <button
                    type="button"
                    onclick={onclose}
                    class="px-4 py-2 text-slate-400 hover:text-white rounded-lg transition-colors cursor-pointer"
                >
                    Cancel
                </button>
                <button
                    type="submit"
                    disabled={saving || deviceId === 0}
                    class="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium px-6 py-2 rounded-lg transition-colors cursor-pointer"
                >
                    {saving ? "Creating..." : "Create"}
                </button>
            </div>
        </form>
    </div>
</div>
