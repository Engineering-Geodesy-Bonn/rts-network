<script lang="ts">
    import { updateRts } from "../api/client";
    import type { RTSResponse } from "../api/types";

    let {
        rts,
        onclose,
        onsaved,
    }: {
        rts: RTSResponse;
        onclose: () => void;
        onsaved: () => void;
    } = $props();

    // Copy initial prop values into local form state
    // svelte-ignore state_referenced_locally
    const init = { ...rts };
    let name = $state(init.name);
    let port = $state(init.port);
    let baudrate = $state(init.baudrate);
    let timeout = $state(init.timeout);
    let parity = $state(init.parity);
    let stopbits = $state(init.stopbits);
    let bytesize = $state(init.bytesize);
    let external_delay = $state(init.external_delay);
    let internal_delay = $state(init.internal_delay);
    let station_x = $state(init.station_x);
    let station_y = $state(init.station_y);
    let station_z = $state(init.station_z);
    let orientation = $state(init.orientation);
    let distance_std_dev = $state(init.distance_std_dev);
    let angle_std_dev = $state(init.angle_std_dev);
    let distance_ppm = $state(init.distance_ppm);

    let saving = $state(false);
    let error = $state("");

    async function handleSubmit() {
        saving = true;
        error = "";
        try {
            await updateRts(rts.id, {
                name,
                port,
                baudrate,
                timeout,
                parity,
                stopbits,
                bytesize,
                external_delay,
                internal_delay,
                station_x,
                station_y,
                station_z,
                orientation,
                distance_std_dev,
                angle_std_dev,
                distance_ppm,
            });
            onsaved();
        } catch (e: any) {
            error = e.message || "Failed to update RTS";
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
        class="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-lg max-h-[90vh] flex flex-col shadow-2xl"
        onclick={(e) => e.stopPropagation()}
        onkeydown={() => {}}
    >
        <div
            class="p-6 border-b border-slate-700 flex items-center justify-between shrink-0"
        >
            <h2 class="text-xl font-semibold">Edit RTS: {rts.name}</h2>
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
            class="p-6 space-y-3 overflow-y-auto"
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

            <!-- General -->
            <div class="grid grid-cols-2 gap-3">
                <div class="col-span-2">
                    <label
                        class="block text-xs font-medium text-slate-400 mb-1"
                        for="e-name">Name</label
                    >
                    <input
                        id="e-name"
                        type="text"
                        bind:value={name}
                        class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                    />
                </div>
                <div class="col-span-2">
                    <label
                        class="block text-xs font-medium text-slate-400 mb-1"
                        for="e-port">Port</label
                    >
                    <input
                        id="e-port"
                        type="text"
                        bind:value={port}
                        class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-blue-500"
                    />
                </div>
            </div>

            <!-- Serial -->
            <h3
                class="text-xs font-semibold text-slate-500 uppercase tracking-wider pt-2"
            >
                Serial
            </h3>
            <div class="grid grid-cols-4 gap-3">
                <div>
                    <label
                        class="block text-xs text-slate-400 mb-1"
                        for="e-baud">Baudrate</label
                    >
                    <input
                        id="e-baud"
                        type="number"
                        bind:value={baudrate}
                        class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                    />
                </div>
                <div>
                    <label
                        class="block text-xs text-slate-400 mb-1"
                        for="e-timeout">Timeout</label
                    >
                    <input
                        id="e-timeout"
                        type="number"
                        bind:value={timeout}
                        class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                    />
                </div>
                <div>
                    <label
                        class="block text-xs text-slate-400 mb-1"
                        for="e-parity">Parity</label
                    >
                    <input
                        id="e-parity"
                        type="text"
                        bind:value={parity}
                        class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                    />
                </div>
                <div>
                    <label
                        class="block text-xs text-slate-400 mb-1"
                        for="e-stop">Stopbits</label
                    >
                    <input
                        id="e-stop"
                        type="number"
                        bind:value={stopbits}
                        class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                    />
                </div>
                <div>
                    <label
                        class="block text-xs text-slate-400 mb-1"
                        for="e-byte">Bytesize</label
                    >
                    <input
                        id="e-byte"
                        type="number"
                        bind:value={bytesize}
                        class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                    />
                </div>
            </div>

            <!-- Station -->
            <h3
                class="text-xs font-semibold text-slate-500 uppercase tracking-wider pt-2"
            >
                Station Position
            </h3>
            <div class="grid grid-cols-4 gap-3">
                <div>
                    <label class="block text-xs text-slate-400 mb-1" for="e-sx"
                        >X</label
                    >
                    <input
                        id="e-sx"
                        type="number"
                        step="any"
                        bind:value={station_x}
                        class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                    />
                </div>
                <div>
                    <label class="block text-xs text-slate-400 mb-1" for="e-sy"
                        >Y</label
                    >
                    <input
                        id="e-sy"
                        type="number"
                        step="any"
                        bind:value={station_y}
                        class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                    />
                </div>
                <div>
                    <label class="block text-xs text-slate-400 mb-1" for="e-sz"
                        >Z</label
                    >
                    <input
                        id="e-sz"
                        type="number"
                        step="any"
                        bind:value={station_z}
                        class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                    />
                </div>
                <div>
                    <label
                        class="block text-xs text-slate-400 mb-1"
                        for="e-orient">Orientation</label
                    >
                    <input
                        id="e-orient"
                        type="number"
                        step="any"
                        bind:value={orientation}
                        class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                    />
                </div>
            </div>

            <!-- Delays & Quality -->
            <h3
                class="text-xs font-semibold text-slate-500 uppercase tracking-wider pt-2"
            >
                Delays & Quality
            </h3>
            <div class="grid grid-cols-2 gap-3">
                <div>
                    <label
                        class="block text-xs text-slate-400 mb-1"
                        for="e-intd">Internal Delay (s)</label
                    >
                    <input
                        id="e-intd"
                        type="number"
                        step="any"
                        bind:value={internal_delay}
                        class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                    />
                </div>
                <div>
                    <label
                        class="block text-xs text-slate-400 mb-1"
                        for="e-extd">External Delay (s)</label
                    >
                    <input
                        id="e-extd"
                        type="number"
                        step="any"
                        bind:value={external_delay}
                        class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                    />
                </div>
                <div>
                    <label
                        class="block text-xs text-slate-400 mb-1"
                        for="e-dstd">Distance Std Dev</label
                    >
                    <input
                        id="e-dstd"
                        type="number"
                        step="any"
                        bind:value={distance_std_dev}
                        class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                    />
                </div>
                <div>
                    <label
                        class="block text-xs text-slate-400 mb-1"
                        for="e-astd">Angle Std Dev</label
                    >
                    <input
                        id="e-astd"
                        type="number"
                        step="any"
                        bind:value={angle_std_dev}
                        class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                    />
                </div>
                <div>
                    <label
                        class="block text-xs text-slate-400 mb-1"
                        for="e-dppm">Distance PPM</label
                    >
                    <input
                        id="e-dppm"
                        type="number"
                        step="any"
                        bind:value={distance_ppm}
                        class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                    />
                </div>
            </div>

            <div class="flex justify-end gap-3 pt-3">
                <button
                    type="button"
                    onclick={onclose}
                    class="px-4 py-2 text-slate-400 hover:text-white rounded-lg transition-colors cursor-pointer"
                    >Cancel</button
                >
                <button
                    type="submit"
                    disabled={saving}
                    class="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium px-6 py-2 rounded-lg transition-colors cursor-pointer"
                >
                    {saving ? "Saving..." : "Save Changes"}
                </button>
            </div>
        </form>
    </div>
</div>
