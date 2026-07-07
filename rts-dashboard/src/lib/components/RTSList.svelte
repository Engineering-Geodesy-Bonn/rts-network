<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import {
        getAllRts,
        deleteRts,
        getDevices,
        getRtsStatus,
        getJob,
        createJob,
        updateJobStatus,
    } from "../api/client";
    import { currentSession } from "../stores/session";
    import type {
        RTSResponse,
        DeviceResponse,
        SessionResponse,
        RTSStatusResponse,
    } from "../api/types";
    import type { RTSJobType } from "../api/types";
    import { RTS_STATUS_POLL_MS, JOB_TYPE_NAMES } from "../constants";
    import RTSForm from "./RTSForm.svelte";
    import RTSSettingsModal from "./RTSSettingsModal.svelte";
    import TrackingSettingsModal from "./TrackingSettingsModal.svelte";

    let rtsList = $state<RTSResponse[]>([]);
    let devices = $state<DeviceResponse[]>([]);
    let statuses = $state<Record<string, RTSStatusResponse>>({});
    let jobTypeMap = $state<Record<string, string>>({});
    let loading = $state(true);
    let error = $state("");
    let showAddForm = $state(false);
    let editingRts = $state<RTSResponse | null>(null);
    let trackingRtsId = $state<string | null>(null);
    let session = $state<SessionResponse | null>(null);
    let actionDropdownId = $state<string | null>(null);
    let statusTimerId: ReturnType<typeof setInterval> | null = null;

    const unsub = currentSession.subscribe((s) => {
        session = s;
    });

    onDestroy(() => {
        unsub();
        stopStatusPolling();
    });

    // ── Data Loading ────────────────────────────────────────
    async function loadData() {
        loading = true;
        error = "";
        try {
            const [rts, devs] = await Promise.all([
                getAllRts(session!.id),
                getDevices(),
            ]);
            rtsList = rts;
            devices = devs;
        } catch (e: any) {
            error = e.message || "Failed to load data";
        } finally {
            loading = false;
        }
    }

    // ── Status Polling ──────────────────────────────────────
    function startStatusPolling() {
        stopStatusPolling();
        pollAllStatuses();
        statusTimerId = setInterval(pollAllStatuses, RTS_STATUS_POLL_MS);
    }

    function stopStatusPolling() {
        if (statusTimerId) {
            clearInterval(statusTimerId);
            statusTimerId = null;
        }
    }

    async function pollAllStatuses() {
        const results = await Promise.allSettled(
            rtsList.map((rts) => getRtsStatus(rts.id)),
        );
        const newStatuses: Record<string, RTSStatusResponse> = {};
        rtsList.forEach((rts, i) => {
            const r = results[i];
            if (r.status === "fulfilled") {
                newStatuses[rts.id] = r.value;
            }
        });
        statuses = newStatuses;

        // Resolve job types for busy RTS whose job_id is not yet cached
        const unknownJobIds = Object.values(newStatuses)
            .filter(
                (s) => s.busy && s.job_id != null && !(s.job_id in jobTypeMap),
            )
            .map((s) => s.job_id!);
        if (unknownJobIds.length > 0) {
            const jobResults = await Promise.allSettled(
                unknownJobIds.map((id) => getJob(id)),
            );
            const updated = { ...jobTypeMap };
            jobResults.forEach((r, i) => {
                if (r.status === "fulfilled") {
                    updated[unknownJobIds[i]] = r.value.job_type;
                }
            });
            jobTypeMap = updated;
        }
    }

    // ── Job Actions ─────────────────────────────────────────
    async function startTracking(rtsId: string) {
        try {
            await createJob({ rts_id: rtsId, job_type: "track_prism" });
        } catch (e: any) {
            error = e.message || "Failed to start tracking";
        }
    }

    async function stopTracking(rtsId: string) {
        const status = statuses[rtsId];
        if (!status?.busy || !status.job_id) return;
        try {
            await updateJobStatus(status.job_id, "finished");
        } catch (e: any) {
            error = e.message || "Failed to stop tracking";
        }
    }

    async function startAllTracking() {
        error = "";
        try {
            const promises = rtsList
                .filter((rts) => !statuses[rts.id]?.busy)
                .map((rts) =>
                    createJob({ rts_id: rts.id, job_type: "track_prism" }),
                );
            await Promise.allSettled(promises);
        } catch (e: any) {
            error = e.message || "Failed to start all";
        }
    }

    async function stopAllTracking() {
        error = "";
        try {
            const promises = rtsList
                .filter(
                    (rts) => statuses[rts.id]?.busy && statuses[rts.id]?.job_id,
                )
                .map((rts) =>
                    updateJobStatus(statuses[rts.id].job_id!, "finished"),
                );
            await Promise.allSettled(promises);
        } catch (e: any) {
            error = e.message || "Failed to stop all";
        }
    }

    async function runAction(rtsId: string, jobType: RTSJobType) {
        actionDropdownId = null;
        try {
            await createJob({ rts_id: rtsId, job_type: jobType });
        } catch (e: any) {
            error =
                e.message ||
                `Failed to run ${JOB_TYPE_NAMES[jobType] || jobType}`;
        }
    }

    // ── CRUD ────────────────────────────────────────────────
    async function handleDelete(id: string) {
        if (!confirm("Delete this RTS station?")) return;
        try {
            await deleteRts(id);
            rtsList = rtsList.filter((r) => r.id !== id);
        } catch (e: any) {
            error = e.message || "Failed to delete RTS";
        }
    }

    function handleCreated() {
        showAddForm = false;
        loadData().then(startStatusPolling);
    }

    function handleUpdated() {
        editingRts = null;
        loadData();
    }

    function getDeviceIp(deviceId: string): string {
        const dev = devices.find((d) => d.id === deviceId);
        return dev?.ip || "Unknown";
    }

    function toggleDropdown(rtsId: string) {
        actionDropdownId = actionDropdownId === rtsId ? null : rtsId;
    }

    // Track how many are busy / idle
    let busyCount = $derived(
        rtsList.filter((rts) => statuses[rts.id]?.busy).length,
    );
    let idleCount = $derived(rtsList.length - busyCount);

    onMount(async () => {
        await loadData();
        startStatusPolling();
    });
</script>

<!-- Close dropdown on outside click -->
<svelte:window
    onclick={() => {
        actionDropdownId = null;
    }}
/>

<div class="max-w-6xl mx-auto">
    <!-- Header -->
    <div class="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
            <h2 class="text-2xl font-bold">RTS Stations</h2>
            <p class="text-sm text-slate-400 mt-1">
                {rtsList.length} station{rtsList.length !== 1 ? "s" : ""}
                {#if busyCount > 0}
                    &middot; <span class="text-green-400">{busyCount} busy</span
                    >
                {/if}
            </p>
        </div>
        <div class="flex flex-wrap gap-2">
            {#if rtsList.length > 0}
                <button
                    onclick={startAllTracking}
                    disabled={idleCount === 0}
                    class="bg-green-600 hover:bg-green-700 disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium px-4 py-2 rounded-lg transition-colors text-sm cursor-pointer"
                >
                    ▶ Start All
                </button>
                <button
                    onclick={stopAllTracking}
                    disabled={busyCount === 0}
                    class="bg-red-600 hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium px-4 py-2 rounded-lg transition-colors text-sm cursor-pointer"
                >
                    ■ Stop All
                </button>
            {/if}
            <button
                onclick={loadData}
                class="text-slate-400 hover:text-white hover:bg-slate-700 px-3 py-2 rounded-lg transition-colors text-sm cursor-pointer"
            >
                ↻ Refresh
            </button>
            <button
                onclick={() => (showAddForm = true)}
                class="bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-2 rounded-lg transition-colors flex items-center gap-2 cursor-pointer"
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
                        d="M12 4v16m8-8H4"
                    />
                </svg>
                Add RTS
            </button>
        </div>
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
    {:else if rtsList.length === 0}
        <div
            class="bg-slate-800 rounded-xl border border-slate-700 p-12 text-center"
        >
            <img
                src="/RTS.png"
                alt="RTS"
                class="h-16 mx-auto mb-3 object-contain"
            />
            <h3 class="text-lg font-medium text-slate-300 mb-1">
                No RTS stations
            </h3>
            <p class="text-slate-500">
                Add a Robotic Total Station to get started.
            </p>
        </div>
    {:else}
        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {#each rtsList as rts (rts.id)}
                {@const status = statuses[rts.id]}
                {@const busy = status?.busy ?? false}
                {@const activeJobType =
                    busy && status?.job_id != null
                        ? (jobTypeMap[status.job_id] ?? null)
                        : null}
                {@const activeJobLabel = activeJobType
                    ? (
                          JOB_TYPE_NAMES[activeJobType] ?? activeJobType
                      ).toUpperCase()
                    : "BUSY"}
                <div
                    class="bg-slate-800 rounded-xl border transition-colors
                        {busy
                        ? 'border-green-500/40'
                        : 'border-slate-700 hover:border-slate-600'}"
                >
                    <!-- Card Header -->
                    <div class="p-4 pb-0 flex items-start justify-between">
                        <div class="flex items-center gap-2">
                            <!-- Status Dot -->
                            <div
                                class="w-2.5 h-2.5 rounded-full shrink-0 mt-1
                                    {busy
                                    ? 'bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.5)]'
                                    : 'bg-slate-600'}"
                            ></div>
                            <div>
                                <h3
                                    class="font-semibold text-lg text-white leading-tight"
                                >
                                    {rts.name}
                                </h3>
                                <span class="text-xs text-slate-500"
                                    >ID: {rts.id.substring(0, 8)} &middot; {getDeviceIp(
                                        rts.device_id,
                                    )}</span
                                >
                            </div>
                        </div>
                        <div class="flex gap-0.5">
                            <button
                                class="text-slate-400 hover:text-blue-400 hover:bg-blue-500/10 p-1.5 rounded-lg transition-colors cursor-pointer"
                                title="Edit RTS settings"
                                onclick={() => (editingRts = rts)}
                            >
                                <svg
                                    class="w-4 h-4"
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
                                class="text-slate-400 hover:text-amber-400 hover:bg-amber-500/10 p-1.5 rounded-lg transition-colors cursor-pointer"
                                title="Tracking settings"
                                onclick={() => (trackingRtsId = rts.id)}
                            >
                                <svg
                                    class="w-4 h-4"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        stroke-linecap="round"
                                        stroke-linejoin="round"
                                        stroke-width="2"
                                        d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                                    />
                                    <path
                                        stroke-linecap="round"
                                        stroke-linejoin="round"
                                        stroke-width="2"
                                        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                                    />
                                </svg>
                            </button>
                            <!-- Actions Dropdown -->
                            <div class="relative">
                                <button
                                    class="text-slate-400 hover:text-white hover:bg-slate-700 p-1.5 rounded-lg transition-colors cursor-pointer"
                                    title="More actions"
                                    onclick={(e) => {
                                        e.stopPropagation();
                                        toggleDropdown(rts.id);
                                    }}
                                >
                                    <svg
                                        class="w-4 h-4"
                                        fill="none"
                                        stroke="currentColor"
                                        viewBox="0 0 24 24"
                                    >
                                        <path
                                            stroke-linecap="round"
                                            stroke-linejoin="round"
                                            stroke-width="2"
                                            d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"
                                        />
                                    </svg>
                                </button>
                                {#if actionDropdownId === rts.id}
                                    <!-- svelte-ignore a11y_no_static_element_interactions -->
                                    <div
                                        class="absolute right-0 top-full mt-1 w-48 bg-slate-700 border border-slate-600 rounded-lg shadow-xl z-30 py-1"
                                        onclick={(e) => e.stopPropagation()}
                                        onkeydown={() => {}}
                                    >
                                        <button
                                            class="w-full text-left px-4 py-2 text-sm text-slate-200 hover:bg-slate-600 transition-colors cursor-pointer"
                                            onclick={() =>
                                                runAction(
                                                    rts.id,
                                                    "test_connection",
                                                )}
                                        >
                                            🔌 Test Connection
                                        </button>
                                        <button
                                            class="w-full text-left px-4 py-2 text-sm text-slate-200 hover:bg-slate-600 transition-colors cursor-pointer"
                                            onclick={() =>
                                                runAction(
                                                    rts.id,
                                                    "change_face",
                                                )}
                                        >
                                            🔄 Change Face
                                        </button>
                                        <button
                                            class="w-full text-left px-4 py-2 text-sm text-slate-200 hover:bg-slate-600 transition-colors cursor-pointer"
                                            onclick={() =>
                                                runAction(
                                                    rts.id,
                                                    "turn_to_target",
                                                )}
                                        >
                                            🎯 Turn to Target
                                        </button>
                                        <button
                                            class="w-full text-left px-4 py-2 text-sm text-slate-200 hover:bg-slate-600 transition-colors cursor-pointer"
                                            onclick={() =>
                                                runAction(
                                                    rts.id,
                                                    "add_static_measurement",
                                                )}
                                        >
                                            📏 Perform static measurement
                                        </button>
                                        <div
                                            class="border-t border-slate-600 my-1"
                                        ></div>
                                        <button
                                            class="w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 transition-colors cursor-pointer"
                                            onclick={() => handleDelete(rts.id)}
                                        >
                                            🗑️ Delete RTS
                                        </button>
                                    </div>
                                {/if}
                            </div>
                        </div>
                    </div>

                    <!-- Live Status Bar -->
                    {#if status}
                        <div
                            class="mx-4 mt-3 px-3 py-2 rounded-lg text-xs font-mono flex items-center justify-between
                                {busy
                                ? 'bg-green-500/10 border border-green-500/20'
                                : 'bg-slate-700/50'}"
                        >
                            <span
                                class={busy
                                    ? "text-green-400 font-semibold"
                                    : "text-slate-500"}
                            >
                                {busy ? `● ${activeJobLabel}` : "○ Idle"}
                            </span>
                            {#if busy}
                                <span class="text-slate-300">
                                    {status.num_measurements} meas &middot; {status.datarate.toFixed(
                                        1,
                                    )} Hz
                                </span>
                            {/if}
                        </div>
                    {/if}

                    <!-- Info -->
                    <div class="p-4 space-y-1.5 text-sm">
                        <div class="flex justify-between">
                            <span class="text-slate-400">Port</span>
                            <span class="text-slate-200 font-mono text-xs"
                                >{rts.port}</span
                            >
                        </div>
                        <div class="flex justify-between">
                            <span class="text-slate-400">Baudrate</span>
                            <span class="text-slate-200"
                                >{rts.baudrate.toLocaleString()}</span
                            >
                        </div>
                        <div class="flex justify-between">
                            <span class="text-slate-400">Station</span>
                            <span class="text-slate-200 font-mono text-xs">
                                ({rts.station_x.toFixed(3)}, {rts.station_y.toFixed(
                                    3,
                                )}, {rts.station_z.toFixed(3)})
                            </span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-slate-400">Orientation</span>
                            <span class="text-slate-200"
                                >{((rts.orientation * 200) / Math.PI).toFixed(
                                    4,
                                )} gon</span
                            >
                        </div>
                    </div>

                    <!-- Quick Actions Row -->
                    <div class="px-4 pb-2 flex gap-2">
                        <button
                            onclick={() => runAction(rts.id, "change_face")}
                            disabled={busy}
                            class="flex-1 bg-slate-700 hover:bg-slate-600 disabled:opacity-40 disabled:cursor-not-allowed text-slate-200 text-xs font-medium py-2 rounded-lg transition-colors cursor-pointer flex items-center justify-center gap-1.5"
                            title="Change Face"
                        >
                            🔄 Change Face
                        </button>
                        <button
                            onclick={() => runAction(rts.id, "turn_to_target")}
                            disabled={busy}
                            class="flex-1 bg-slate-700 hover:bg-slate-600 disabled:opacity-40 disabled:cursor-not-allowed text-slate-200 text-xs font-medium py-2 rounded-lg transition-colors cursor-pointer flex items-center justify-center gap-1.5"
                            title="Turn to Target"
                        >
                            🎯 Turn to Target
                        </button>
                    </div>

                    <!-- Start / Stop Button -->
                    <div class="px-4 pb-4">
                        {#if busy}
                            <button
                                onclick={() => stopTracking(rts.id)}
                                class="w-full bg-red-600 hover:bg-red-700 text-white font-medium py-2.5 rounded-lg transition-colors cursor-pointer flex items-center justify-center gap-2"
                            >
                                <svg
                                    class="w-4 h-4"
                                    fill="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <rect
                                        x="6"
                                        y="6"
                                        width="12"
                                        height="12"
                                        rx="1"
                                    />
                                </svg>
                                Stop {activeJobType
                                    ? (JOB_TYPE_NAMES[activeJobType] ?? "Job")
                                    : "Job"}
                            </button>
                        {:else}
                            <button
                                onclick={() => startTracking(rts.id)}
                                class="w-full bg-green-600 hover:bg-green-700 text-white font-medium py-2.5 rounded-lg transition-colors cursor-pointer flex items-center justify-center gap-2"
                            >
                                <svg
                                    class="w-4 h-4"
                                    fill="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <polygon points="5,3 19,12 5,21" />
                                </svg>
                                Start Tracking
                            </button>
                        {/if}
                    </div>
                </div>
            {/each}
        </div>
    {/if}
</div>

{#if showAddForm && session}
    <RTSForm
        {devices}
        sessionId={session.id}
        onclose={() => (showAddForm = false)}
        onsaved={handleCreated}
    />
{/if}

{#if editingRts}
    <RTSSettingsModal
        rts={editingRts}
        onclose={() => (editingRts = null)}
        onsaved={handleUpdated}
    />
{/if}

{#if trackingRtsId !== null}
    <TrackingSettingsModal
        rtsId={trackingRtsId}
        onclose={() => (trackingRtsId = null)}
    />
{/if}
