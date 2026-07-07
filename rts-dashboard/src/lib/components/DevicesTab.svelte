<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import { getDevices } from "../api/client";
    import type { DeviceResponse } from "../api/types";

    let devices = $state<DeviceResponse[]>([]);
    let loading = $state(true);
    let error = $state("");
    let pollTimerId: ReturnType<typeof setInterval> | null = null;
    let now = $state(Date.now());
    let tickTimerId: ReturnType<typeof setInterval> | null = null;

    async function loadDevices() {
        error = "";
        try {
            devices = await getDevices();
        } catch (e: any) {
            error = e.message || "Failed to load devices";
        } finally {
            loading = false;
        }
    }

    function startPolling() {
        stopPolling();
        pollTimerId = setInterval(loadDevices, 5000);
    }

    function stopPolling() {
        if (pollTimerId) {
            clearInterval(pollTimerId);
            pollTimerId = null;
        }
    }

    function formatLastSeen(ts: number): string {
        return new Date(ts * 1000).toLocaleString();
    }

    function timeAgo(ts: number): string {
        const diffMs = now - ts * 1000;
        if (diffMs < 0) return "just now";
        const seconds = Math.floor(diffMs / 1000);
        if (seconds < 60) return `${seconds}s ago`;
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) return `${minutes}m ${seconds % 60}s ago`;
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours}h ${minutes % 60}m ago`;
        const days = Math.floor(hours / 24);
        return `${days}d ${hours % 24}h ago`;
    }

    function isOnline(ts: number): boolean {
        return now - ts * 1000 < 30_000; // seen within last 30s
    }

    onMount(async () => {
        await loadDevices();
        startPolling();
        // Update "now" every second for live time-ago display
        tickTimerId = setInterval(() => {
            now = Date.now();
        }, 1000);
    });

    onDestroy(() => {
        stopPolling();
        if (tickTimerId) clearInterval(tickTimerId);
    });
</script>

<div class="max-w-6xl mx-auto">
    <!-- Header -->
    <div class="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
            <h2 class="text-2xl font-bold">Devices</h2>
            <p class="text-sm text-slate-400 mt-1">
                {devices.length} device{devices.length !== 1 ? "s" : ""} registered
                {#if devices.filter((d) => isOnline(d.last_seen)).length > 0}
                    &middot; <span class="text-green-400"
                        >{devices.filter((d) => isOnline(d.last_seen)).length} online</span
                    >
                {/if}
            </p>
        </div>
        <button
            onclick={loadDevices}
            class="text-slate-400 hover:text-white hover:bg-slate-700 px-3 py-2 rounded-lg transition-colors text-sm cursor-pointer"
        >
            ↻ Refresh
        </button>
    </div>

    {#if error}
        <div
            class="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg mb-4 text-sm"
        >
            {error}
            <button
                onclick={() => (error = "")}
                class="ml-2 underline cursor-pointer">dismiss</button
            >
        </div>
    {/if}

    {#if loading}
        <div class="flex items-center justify-center py-12">
            <div
                class="inline-block w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full animate-spin"
            ></div>
        </div>
    {:else if devices.length === 0}
        <div
            class="bg-slate-800 rounded-xl border border-slate-700 p-12 text-center"
        >
            <div class="text-4xl mb-3">🖥️</div>
            <h3 class="text-lg font-medium text-slate-300 mb-1">
                No devices found
            </h3>
            <p class="text-slate-500">No devices have been registered yet.</p>
        </div>
    {:else}
        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {#each devices as device (device.id)}
                {@const online = isOnline(device.last_seen)}
                <div
                    class="bg-slate-800 rounded-xl border transition-colors
                        {online ? 'border-green-500/40' : 'border-slate-700'}"
                >
                    <div class="p-5">
                        <!-- Top row: status + ID -->
                        <div class="flex items-center justify-between mb-3">
                            <div class="flex items-center gap-2.5">
                                <div
                                    class="w-2.5 h-2.5 rounded-full shrink-0
                                        {online
                                        ? 'bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.5)]'
                                        : 'bg-slate-600'}"
                                ></div>
                                <span
                                    class="text-xs font-medium px-2 py-0.5 rounded-full
                                        {online
                                        ? 'bg-green-500/10 text-green-400 border border-green-500/20'
                                        : 'bg-slate-700 text-slate-400'}"
                                >
                                    {online ? "Online" : "Offline"}
                                </span>
                            </div>
                            <span class="text-xs text-slate-600 font-mono"
                                >ID: {device.id.substring(0, 8)}</span
                            >
                        </div>

                        <!-- IP address -->
                        <div class="mb-4">
                            <div
                                class="text-lg font-semibold text-white font-mono"
                            >
                                {device.ip}
                            </div>
                        </div>

                        <!-- Details -->
                        <div class="space-y-2 text-sm">
                            <div class="flex justify-between">
                                <span class="text-slate-400">Last Seen</span>
                                <span class="text-slate-200 text-xs"
                                    >{formatLastSeen(device.last_seen)}</span
                                >
                            </div>
                            <div class="flex justify-between">
                                <span class="text-slate-400">Time Ago</span>
                                <span
                                    class="text-xs font-mono
                                        {online
                                        ? 'text-green-400'
                                        : 'text-amber-400'}"
                                >
                                    {timeAgo(device.last_seen)}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            {/each}
        </div>
    {/if}
</div>
