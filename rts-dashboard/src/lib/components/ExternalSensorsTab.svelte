<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import {
        getExternalSensors,
        updateExternalSensor,
        deleteExternalSensor,
    } from "../api/client";
    import type { ExternalSensorResponse } from "../api/types";

    let sensors = $state<ExternalSensorResponse[]>([]);
    let loading = $state(true);
    let error = $state("");
    let successMessage = $state("");
    let editingSensorId = $state<number | null>(null);
    let draftName = $state("");
    let savingSensorId = $state<number | null>(null);
    let deletingSensorId = $state<number | null>(null);
    let now = $state(Date.now());
    let pollTimerId: ReturnType<typeof setInterval> | null = null;
    let tickTimerId: ReturnType<typeof setInterval> | null = null;

    async function loadSensors() {
        loading = true;
        error = "";
        try {
            sensors = await getExternalSensors();
        } catch (e: any) {
            error = e.message || "Failed to load external sensors";
        } finally {
            loading = false;
        }
    }

    async function pollSensors() {
        try {
            sensors = await getExternalSensors();
        } catch {
            // silently ignore poll errors
        }
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

    function isRecent(ts: number): boolean {
        return now - ts * 1000 < 30_000;
    }

    function beginEdit(sensor: ExternalSensorResponse) {
        editingSensorId = sensor.id;
        draftName = sensor.name;
        successMessage = "";
    }

    function cancelEdit() {
        editingSensorId = null;
        draftName = "";
    }

    async function handleRename(sensor: ExternalSensorResponse) {
        const trimmedName = draftName.trim();
        if (!trimmedName || trimmedName === sensor.name) {
            cancelEdit();
            return;
        }

        savingSensorId = sensor.id;
        error = "";
        successMessage = "";
        try {
            const updatedSensor = await updateExternalSensor(
                sensor.id,
                trimmedName,
            );
            sensors = sensors.map((item) =>
                item.id === sensor.id ? updatedSensor : item,
            );
            successMessage = `Renamed sensor to ${updatedSensor.name}`;
            cancelEdit();
        } catch (e: any) {
            error = e.message || "Failed to rename external sensor";
        } finally {
            savingSensorId = null;
        }
    }

    async function handleDelete(sensor: ExternalSensorResponse) {
        if (!confirm(`Delete external sensor \"${sensor.name}\"?`)) return;

        deletingSensorId = sensor.id;
        error = "";
        successMessage = "";
        try {
            await deleteExternalSensor(sensor.id);
            sensors = sensors.filter((item) => item.id !== sensor.id);
            if (editingSensorId === sensor.id) {
                cancelEdit();
            }
            successMessage = `Deleted sensor ${sensor.name}`;
        } catch (e: any) {
            error = e.message || "Failed to delete external sensor";
        } finally {
            deletingSensorId = null;
        }
    }

    onMount(async () => {
        await loadSensors();
        pollTimerId = setInterval(pollSensors, 5000);
        tickTimerId = setInterval(() => {
            now = Date.now();
        }, 1000);
    });

    onDestroy(() => {
        if (pollTimerId) clearInterval(pollTimerId);
        if (tickTimerId) clearInterval(tickTimerId);
    });
</script>

<div class="max-w-6xl mx-auto">
    <div class="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
            <h2 class="text-2xl font-bold">External Sensors</h2>
            <p class="text-sm text-slate-400 mt-1">
                {sensors.length} sensor{sensors.length !== 1 ? "s" : ""} registered
            </p>
        </div>
        <button
            onclick={loadSensors}
            disabled={loading}
            class="text-slate-400 hover:text-white hover:bg-slate-700 disabled:opacity-50 px-3 py-2 rounded-lg transition-colors text-sm cursor-pointer"
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

    {#if successMessage}
        <div
            class="bg-green-500/10 border border-green-500/30 text-green-400 px-4 py-3 rounded-lg mb-4 text-sm"
        >
            {successMessage}
            <button
                onclick={() => (successMessage = "")}
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
    {:else if sensors.length === 0}
        <div
            class="bg-slate-800 rounded-xl border border-slate-700 p-12 text-center"
        >
            <div class="text-4xl mb-3">📡</div>
            <h3 class="text-lg font-medium text-slate-300 mb-1">
                No external sensors found
            </h3>
            <p class="text-slate-500">
                External sensors will appear here once they are available
                through the API.
            </p>
        </div>
    {:else}
        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {#each sensors as sensor (sensor.id)}
                {@const isEditing = editingSensorId === sensor.id}
                {@const isSaving = savingSensorId === sensor.id}
                {@const isDeleting = deletingSensorId === sensor.id}
                {@const lastSeenTs =
                    typeof sensor.last_seen === "number"
                        ? sensor.last_seen
                        : null}
                {@const recent = lastSeenTs !== null && isRecent(lastSeenTs)}

                <div
                    class="bg-slate-800 rounded-xl border transition-colors
                    {recent
                        ? 'border-green-500/40'
                        : 'border-slate-700 hover:border-slate-600'}"
                >
                    <div class="p-5">
                        <div
                            class="flex items-start justify-between gap-3 mb-4"
                        >
                            <div class="min-w-0 flex-1">
                                {#if isEditing}
                                    <form
                                        class="space-y-3"
                                        onsubmit={(event) => {
                                            event.preventDefault();
                                            handleRename(sensor);
                                        }}
                                    >
                                        <input
                                            bind:value={draftName}
                                            maxlength="120"
                                            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors"
                                        />
                                        <div class="flex gap-2">
                                            <button
                                                type="submit"
                                                disabled={isSaving ||
                                                    !draftName.trim()}
                                                class="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-3 py-2 rounded-lg transition-colors cursor-pointer"
                                            >
                                                {isSaving
                                                    ? "Saving..."
                                                    : "Save"}
                                            </button>
                                            <button
                                                type="button"
                                                onclick={cancelEdit}
                                                disabled={isSaving}
                                                class="text-slate-400 hover:text-white hover:bg-slate-700 disabled:opacity-50 text-sm px-3 py-2 rounded-lg transition-colors cursor-pointer"
                                            >
                                                Cancel
                                            </button>
                                        </div>
                                    </form>
                                {:else}
                                    <div>
                                        <div
                                            class="flex items-center gap-2 mb-0.5"
                                        >
                                            {#if lastSeenTs !== null}
                                                <div
                                                    class="w-2.5 h-2.5 rounded-full shrink-0
                                                    {recent
                                                        ? 'bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.5)]'
                                                        : 'bg-slate-600'}"
                                                ></div>
                                            {/if}
                                            <h3
                                                class="font-semibold text-lg text-white leading-tight truncate"
                                            >
                                                {sensor.name}
                                            </h3>
                                        </div>
                                        <p class="text-xs text-slate-500 mt-1">
                                            ID: {sensor.id}
                                        </p>
                                    </div>
                                {/if}
                            </div>

                            {#if !isEditing}
                                <div class="flex items-center gap-1 shrink-0">
                                    <button
                                        onclick={() => beginEdit(sensor)}
                                        class="text-slate-400 hover:text-blue-400 hover:bg-blue-500/10 p-2 rounded-lg transition-colors cursor-pointer"
                                        title="Rename sensor"
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
                                                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                                            />
                                        </svg>
                                    </button>
                                    <button
                                        onclick={() => handleDelete(sensor)}
                                        disabled={isDeleting}
                                        class="text-slate-400 hover:text-red-400 hover:bg-red-500/10 disabled:opacity-50 disabled:cursor-not-allowed p-2 rounded-lg transition-colors cursor-pointer"
                                        title="Delete sensor"
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
                                                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                                            />
                                        </svg>
                                    </button>
                                </div>
                            {/if}
                        </div>

                        {#if !isEditing}
                            <div class="space-y-2 text-sm">
                                {#if sensor.ip != null}
                                    <div class="flex justify-between gap-3">
                                        <span class="text-slate-400">IP</span>
                                        <span
                                            class="text-slate-200 font-mono uppercase"
                                        >
                                            {sensor.ip}
                                        </span>
                                    </div>
                                {/if}
                                {#if lastSeenTs !== null}
                                    <div class="flex justify-between gap-3">
                                        <span class="text-slate-400"
                                            >Last Seen</span
                                        >
                                        <span
                                            class="text-xs font-mono
                                            {recent
                                                ? 'text-green-400'
                                                : 'text-amber-400'}"
                                        >
                                            {timeAgo(lastSeenTs)}
                                        </span>
                                    </div>
                                {/if}
                            </div>
                        {/if}
                    </div>
                </div>
            {/each}
        </div>
    {/if}
</div>
