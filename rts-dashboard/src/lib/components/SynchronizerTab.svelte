<script lang="ts">
    import { onMount, onDestroy, tick } from "svelte";
    import { Chart, registerables } from "chart.js";
    import {
        getExternalSensors,
        getAllRts,
        getSensorRoles,
        setSensorRoles,
        getSynchronizerState,
        resetSynchronizer,
    } from "../api/client";
    import { currentSession } from "../stores/session";
    import type {
        ExternalSensorResponse,
        RTSResponse,
        SessionResponse,
        SensorRolesResponse,
    } from "../api/types";

    Chart.register(...registerables);

    // ── Session ──────────────────────────────────────────────
    let session = $state<SessionResponse | null>(null);
    const unsubSession = currentSession.subscribe((s) => {
        session = s;
    });

    // ── Data ─────────────────────────────────────────────────
    let externalSensors = $state<ExternalSensorResponse[]>([]);
    let rtsList = $state<RTSResponse[]>([]);
    let savedRoles = $state<SensorRolesResponse>({
        primary_sensor_id: null,
        secondary_sensor_id: null,
    });
    let draftPrimary = $state<string | null>(null);
    let draftSecondary = $state<string | null>(null);
    let rolesChanged = $derived(
        draftPrimary !== savedRoles.primary_sensor_id ||
            draftSecondary !== savedRoles.secondary_sensor_id,
    );
    let activeSensors = $derived(
        externalSensors.filter((s) => s.logging_active),
    );

    // ── UI ────────────────────────────────────────────────────
    let loading = $state(true);
    let error = $state("");
    let successMessage = $state("");
    let saving = $state(false);
    let resetting = $state(false);
    let now = $state(Date.now());

    // ── Chart data ────────────────────────────────────────────
    const MAX_HISTORY = 120;
    let stateHistory = $state<
        Array<{ ts: number; values: Record<string, number> }>
    >([]);
    let chartFields = $state<string[]>([]);
    let stateFields = $derived(chartFields.filter((f) => !isStdField(f)));

    const chartMap = new Map<string, Chart>();

    let pollTimerId: ReturnType<typeof setInterval> | null = null;
    let tickTimerId: ReturnType<typeof setInterval> | null = null;

    // ── Helpers ───────────────────────────────────────────────
    function isStdField(f: string): boolean {
        return (
            f.startsWith("sigma_") ||
            f.endsWith("_std") ||
            f.endsWith("_std_dev")
        );
    }

    function sigmaBase(f: string): string {
        if (f.startsWith("sigma_")) return f.slice(6);
        if (f.endsWith("_std_dev")) return f.slice(0, -8);
        if (f.endsWith("_std")) return f.slice(0, -4);
        return f;
    }

    function chartColorBand(i: number): string {
        const hex = COLORS[i % COLORS.length];
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r},${g},${b},0.15)`;
    }

    function extId(s: ExternalSensorResponse): string {
        return s.id;
    }

    function findLabel(id: string | null): string {
        if (!id) return "";
        const ext = externalSensors.find((s) => extId(s) === id);
        if (ext) return ext.name;
        const rts = rtsList.find((r) => r.id === id);
        if (rts) return rts.name;
        return id.length > 16 ? `${id.slice(0, 12)}…` : id;
    }

    function findKind(id: string | null): "External" | "RTS" | null {
        if (!id) return null;
        if (externalSensors.some((s) => extId(s) === id)) return "External";
        if (rtsList.some((r) => r.id === id)) return "RTS";
        return null;
    }

    function timeAgo(ts: number): string {
        const diff = now - ts * 1000;
        if (diff < 0) return "just now";
        const s = Math.floor(diff / 1000);
        if (s < 60) return `${s}s ago`;
        const m = Math.floor(s / 60);
        if (m < 60) return `${m}m ${s % 60}s ago`;
        const h = Math.floor(m / 60);
        return `${h}h ${m % 60}m ago`;
    }

    function isRecent(ts: number): boolean {
        return now - ts * 1000 < 30_000;
    }

    // ── Loading ───────────────────────────────────────────────
    async function loadAll() {
        loading = true;
        error = "";
        try {
            const [ext, rts, rolesData] = await Promise.all([
                getExternalSensors(),
                session
                    ? getAllRts(session.id)
                    : Promise.resolve([] as RTSResponse[]),
                getSensorRoles().catch(
                    () =>
                        ({
                            primary_sensor_id: null,
                            secondary_sensor_id: null,
                        }) as SensorRolesResponse,
                ),
            ]);
            externalSensors = ext;
            rtsList = rts;
            savedRoles = rolesData;
            draftPrimary = rolesData.primary_sensor_id;
            draftSecondary = rolesData.secondary_sensor_id;
        } catch (e: any) {
            error = e.message || "Failed to load data";
        } finally {
            loading = false;
        }
    }

    // ── Role assignment ───────────────────────────────────────
    function assignPrimary(id: string) {
        if (draftPrimary === id) {
            draftPrimary = null;
        } else {
            if (draftSecondary === id) draftSecondary = null;
            draftPrimary = id;
        }
    }

    function assignSecondary(id: string) {
        if (draftSecondary === id) {
            draftSecondary = null;
        } else {
            if (draftPrimary === id) draftPrimary = null;
            draftSecondary = id;
        }
    }

    async function saveRoles() {
        saving = true;
        error = "";
        try {
            await setSensorRoles(draftPrimary, draftSecondary);
            savedRoles = {
                primary_sensor_id: draftPrimary,
                secondary_sensor_id: draftSecondary,
            };
            successMessage = "Sensor roles saved";
            setTimeout(() => {
                successMessage = "";
            }, 3000);
        } catch (e: any) {
            error = e.message || "Failed to save roles";
        } finally {
            saving = false;
        }
    }

    async function handleReset() {
        if (
            !confirm(
                "Reset the synchronizer? This will clear all accumulated state.",
            )
        )
            return;
        resetting = true;
        error = "";
        try {
            await resetSynchronizer();
            stateHistory = [];
            chartFields = [];
            rebuildDatasets();
            successMessage = "Synchronizer reset";
            setTimeout(() => {
                successMessage = "";
            }, 3000);
        } catch (e: any) {
            error = e.message || "Failed to reset synchronizer";
        } finally {
            resetting = false;
        }
    }

    // ── Chart ─────────────────────────────────────────────────
    const COLORS = [
        "#3b82f6",
        "#22c55e",
        "#f59e0b",
        "#ef4444",
        "#a855f7",
        "#06b6d4",
    ];
    function chartColor(i: number) {
        return COLORS[i % COLORS.length];
    }

    const darkGrid = { color: "#1e293b" };
    const tickStyle = { color: "#64748b", font: { size: 10 as number } };
    const legendStyle = {
        labels: { color: "#94a3b8", font: { size: 11 as number } },
    };
    const tooltipStyle = {
        backgroundColor: "#1e293b",
        borderColor: "#334155",
        borderWidth: 1,
        titleColor: "#f1f5f9",
        bodyColor: "#cbd5e1",
    };

    function makeChartOpts(yLabel: string) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 0 } as const,
            interaction: { mode: "index" as const, intersect: false },
            plugins: {
                legend: {
                    labels: {
                        ...legendStyle.labels,
                        filter: (item: any) =>
                            !item.text.endsWith(" −σ") &&
                            !item.text.endsWith(" +σ"),
                    },
                },
                tooltip: tooltipStyle,
            },
            scales: {
                x: {
                    ticks: { ...tickStyle, maxTicksLimit: 8 },
                    grid: darkGrid,
                },
                y: {
                    title: {
                        display: true,
                        text: yLabel,
                        color: "#94a3b8",
                        font: { size: 11 },
                    },
                    ticks: tickStyle,
                    grid: darkGrid,
                },
            },
        };
    }

    // ── Chart actions & helpers ──────────────────────────────
    function fieldChart(canvas: HTMLCanvasElement, field: string) {
        chartMap.get(field)?.destroy();
        const i = stateFields.indexOf(field);
        const ci = i >= 0 ? i : 0;
        const chart = new Chart(canvas, {
            type: "line",
            data: { labels: [], datasets: [] },
            options: makeChartOpts(field),
        });
        chartMap.set(field, chart);
        rebuildFieldChart(field, chart, ci);
        return {
            destroy() {
                chartMap.get(field)?.destroy();
                chartMap.delete(field);
            },
        };
    }

    function rebuildFieldChart(field: string, chart: Chart, colorIdx: number) {
        const labels = stateHistory.map((s) =>
            new Date(s.ts).toLocaleTimeString(),
        );
        const sigmaField = chartFields.find(
            (f) => isStdField(f) && sigmaBase(f) === field,
        );
        const datasets: any[] = [];

        if (sigmaField) {
            datasets.push({
                label: `${field} −σ`,
                data: stateHistory.map((s) => {
                    const v = s.values[field];
                    const sig = s.values[sigmaField];
                    return v != null && sig != null ? v - sig : null;
                }),
                borderWidth: 0,
                fill: "+1",
                backgroundColor: chartColorBand(colorIdx),
                pointRadius: 0,
                tension: 0.3,
                spanGaps: true,
            });
            datasets.push({
                label: `${field} +σ`,
                data: stateHistory.map((s) => {
                    const v = s.values[field];
                    const sig = s.values[sigmaField];
                    return v != null && sig != null ? v + sig : null;
                }),
                borderWidth: 0,
                fill: false,
                backgroundColor: "transparent",
                pointRadius: 0,
                tension: 0.3,
                spanGaps: true,
            });
        }
        datasets.push({
            label: field,
            data: stateHistory.map((s) => s.values[field] ?? null),
            borderColor: chartColor(colorIdx),
            backgroundColor: "transparent",
            borderWidth: 2,
            fill: false,
            pointRadius: 0,
            tension: 0.3,
            spanGaps: true,
        });

        chart.data.labels = labels;
        chart.data.datasets = datasets;
        chart.update("none");
    }

    function rebuildDatasets() {
        stateFields.forEach((field, i) => {
            const chart = chartMap.get(field);
            if (chart) rebuildFieldChart(field, chart, i);
        });
    }

    async function pollState() {
        try {
            const state = await getSynchronizerState();
            const numericEntries: [string, number][] = Object.entries(
                state,
            ).filter(
                (e): e is [string, number] =>
                    typeof e[1] === "number" && Number.isFinite(e[1]),
            );
            if (numericEntries.length === 0) return;

            const snapshot = {
                ts: Date.now(),
                values: Object.fromEntries(numericEntries),
            };
            const newFields = numericEntries.map(([k]) => k);
            const fieldsChanged =
                newFields.length !== chartFields.length ||
                newFields.some((f, i) => f !== chartFields[i]);

            stateHistory = [
                ...stateHistory.slice(-(MAX_HISTORY - 1)),
                snapshot,
            ];
            if (fieldsChanged) {
                chartFields = newFields;
                await tick(); // let Svelte mount new canvas elements before updating
            }
            rebuildDatasets();
        } catch {
            // silently ignore poll errors
        }
    }

    // ── Lifecycle ─────────────────────────────────────────────
    onMount(async () => {
        await loadAll();
        await pollState();
        pollTimerId = setInterval(pollState, 2000);
        tickTimerId = setInterval(() => {
            now = Date.now();
        }, 1000);
    });

    onDestroy(() => {
        unsubSession();
        chartMap.forEach((c) => c.destroy());
        chartMap.clear();
        if (pollTimerId) clearInterval(pollTimerId);
        if (tickTimerId) clearInterval(tickTimerId);
    });
</script>

<div class="max-w-6xl mx-auto space-y-6">
    <!-- Header -->
    <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
            <h2 class="text-2xl font-bold">Synchronizer</h2>
            <p class="text-sm text-slate-400 mt-1">
                Assign sensor roles and monitor synchronization state
            </p>
        </div>
        <div class="flex flex-wrap gap-2">
            {#if rolesChanged}
                <button
                    onclick={saveRoles}
                    disabled={saving}
                    class="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium px-4 py-2 rounded-lg transition-colors text-sm cursor-pointer"
                >
                    {saving ? "Saving…" : "Save Roles"}
                </button>
            {/if}
            <button
                onclick={handleReset}
                disabled={resetting}
                class="bg-red-600/80 hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium px-4 py-2 rounded-lg transition-colors text-sm cursor-pointer"
            >
                {resetting ? "Resetting…" : "↺ Reset"}
            </button>
            <button
                onclick={loadAll}
                disabled={loading}
                class="text-slate-400 hover:text-white hover:bg-slate-700 disabled:opacity-50 px-3 py-2 rounded-lg transition-colors text-sm cursor-pointer"
            >
                ↻ Refresh
            </button>
        </div>
    </div>

    <!-- Banners -->
    {#if error}
        <div
            class="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg text-sm"
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
            class="bg-green-500/10 border border-green-500/30 text-green-400 px-4 py-3 rounded-lg text-sm"
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
    {:else}
        <!-- ── Role Assignment Slots ──────────────────────── -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <!-- Primary -->
            <div
                class="bg-slate-800 rounded-xl border p-4
                    {draftPrimary ? 'border-blue-500/50' : 'border-slate-700'}"
            >
                <div class="flex items-center justify-between mb-3">
                    <span
                        class="text-xs font-semibold uppercase tracking-wider text-blue-400"
                        >Primary</span
                    >
                    {#if draftPrimary !== null}
                        <button
                            onclick={() => (draftPrimary = null)}
                            class="text-slate-500 hover:text-slate-300 text-xs px-2 py-1 rounded hover:bg-slate-700 cursor-pointer transition-colors"
                            >✕ Clear</button
                        >
                    {/if}
                </div>
                {#if draftPrimary !== null}
                    <p class="font-semibold text-white truncate">
                        {findLabel(draftPrimary)}
                    </p>
                    <div class="flex items-center gap-2 mt-1.5 min-w-0">
                        {#if findKind(draftPrimary)}
                            <span
                                class="text-xs px-1.5 py-0.5 rounded shrink-0
                                    {findKind(draftPrimary) === 'External'
                                    ? 'bg-purple-500/20 text-purple-300'
                                    : 'bg-blue-500/20 text-blue-300'}"
                            >
                                {findKind(draftPrimary)}
                            </span>
                        {/if}
                        <span class="text-xs text-slate-500 font-mono truncate"
                            >{draftPrimary}</span
                        >
                    </div>
                {:else}
                    <p class="text-sm text-slate-500 leading-relaxed">
                        No sensor assigned.<br />Click a sensor below to assign.
                    </p>
                {/if}
            </div>

            <!-- Secondary -->
            <div
                class="bg-slate-800 rounded-xl border p-4
                    {draftSecondary
                    ? 'border-amber-500/50'
                    : 'border-slate-700'}"
            >
                <div class="flex items-center justify-between mb-3">
                    <span
                        class="text-xs font-semibold uppercase tracking-wider text-amber-400"
                        >Secondary</span
                    >
                    {#if draftSecondary !== null}
                        <button
                            onclick={() => (draftSecondary = null)}
                            class="text-slate-500 hover:text-slate-300 text-xs px-2 py-1 rounded hover:bg-slate-700 cursor-pointer transition-colors"
                            >✕ Clear</button
                        >
                    {/if}
                </div>
                {#if draftSecondary !== null}
                    <p class="font-semibold text-white truncate">
                        {findLabel(draftSecondary)}
                    </p>
                    <div class="flex items-center gap-2 mt-1.5 min-w-0">
                        {#if findKind(draftSecondary)}
                            <span
                                class="text-xs px-1.5 py-0.5 rounded shrink-0
                                    {findKind(draftSecondary) === 'External'
                                    ? 'bg-purple-500/20 text-purple-300'
                                    : 'bg-blue-500/20 text-blue-300'}"
                            >
                                {findKind(draftSecondary)}
                            </span>
                        {/if}
                        <span class="text-xs text-slate-500 font-mono truncate"
                            >{draftSecondary}</span
                        >
                    </div>
                {:else}
                    <p class="text-sm text-slate-500 leading-relaxed">
                        No sensor assigned.<br />Click a sensor below to assign.
                    </p>
                {/if}
            </div>
        </div>

        <!-- ── Sensor Picker ──────────────────────────────── -->
        <div class="space-y-5">
            {#if rtsList.length > 0}
                <div>
                    <h3
                        class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3"
                    >
                        RTS Stations
                    </h3>
                    <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                        {#each rtsList as rts (rts.id)}
                            {@const sid = rts.id}
                            {@const isPrimary = draftPrimary === sid}
                            {@const isSecondary = draftSecondary === sid}
                            <div
                                class="bg-slate-800 rounded-xl border p-4 transition-colors
                                    {isPrimary
                                    ? 'border-blue-500/60'
                                    : isSecondary
                                      ? 'border-amber-500/60'
                                      : 'border-slate-700 hover:border-slate-600'}"
                            >
                                <h4
                                    class="font-semibold text-white truncate text-sm mb-1"
                                >
                                    {rts.name}
                                </h4>
                                <div class="flex items-center gap-2">
                                    <span
                                        class="text-xs px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300"
                                        >RTS</span
                                    >
                                    <span class="text-xs text-slate-500"
                                        >ID: {rts.id}</span
                                    >
                                </div>
                                <div
                                    class="flex gap-1.5 mt-3 pt-3 border-t border-slate-700/50"
                                >
                                    <button
                                        onclick={() => assignPrimary(sid)}
                                        class="flex-1 text-xs py-1.5 rounded-lg transition-colors cursor-pointer
                                            {isPrimary
                                            ? 'bg-blue-600 text-white font-medium'
                                            : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}"
                                    >
                                        Primary
                                    </button>
                                    <button
                                        onclick={() => assignSecondary(sid)}
                                        class="flex-1 text-xs py-1.5 rounded-lg transition-colors cursor-pointer
                                            {isSecondary
                                            ? 'bg-amber-600 text-white font-medium'
                                            : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}"
                                    >
                                        Secondary
                                    </button>
                                </div>
                            </div>
                        {/each}
                    </div>
                </div>
            {/if}

            {#if activeSensors.length > 0}
                <div>
                    <h3
                        class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3"
                    >
                        External Sensors
                    </h3>
                    <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                        {#each activeSensors as sensor (sensor.id)}
                            {@const sid = extId(sensor)}
                            {@const isPrimary = draftPrimary === sid}
                            {@const isSecondary = draftSecondary === sid}
                            {@const recent = isRecent(sensor.last_seen)}
                            <div
                                class="bg-slate-800 rounded-xl border p-4 transition-colors
                                    {isPrimary
                                    ? 'border-blue-500/60'
                                    : isSecondary
                                      ? 'border-amber-500/60'
                                      : 'border-slate-700 hover:border-slate-600'}"
                            >
                                <div class="flex items-center gap-2 mb-1">
                                    <div
                                        class="w-2 h-2 rounded-full shrink-0
                                            {recent
                                            ? 'bg-green-400 shadow-[0_0_5px_rgba(74,222,128,0.5)]'
                                            : 'bg-slate-600'}"
                                    ></div>
                                    <h4
                                        class="font-semibold text-white truncate text-sm"
                                    >
                                        {sensor.name}
                                    </h4>
                                </div>
                                <div class="flex items-center gap-2 mb-2">
                                    <span
                                        class="text-xs px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300"
                                        >External</span
                                    >
                                    <span class="text-xs text-slate-500"
                                        >ID: {sensor.id}</span
                                    >
                                </div>
                                <div class="space-y-1 text-xs">
                                    <div class="flex justify-between">
                                        <span class="text-slate-400">IP</span>
                                        <span
                                            class="text-slate-200 font-mono uppercase"
                                            >{sensor.ip}</span
                                        >
                                    </div>
                                    <div class="flex justify-between">
                                        <span class="text-slate-400"
                                            >Last Seen</span
                                        >
                                        <span
                                            class="font-mono {recent
                                                ? 'text-green-400'
                                                : 'text-amber-400'}"
                                            >{timeAgo(sensor.last_seen)}</span
                                        >
                                    </div>
                                </div>
                                <div
                                    class="flex gap-1.5 mt-3 pt-3 border-t border-slate-700/50"
                                >
                                    <button
                                        onclick={() => assignPrimary(sid)}
                                        class="flex-1 text-xs py-1.5 rounded-lg transition-colors cursor-pointer
                                            {isPrimary
                                            ? 'bg-blue-600 text-white font-medium'
                                            : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}"
                                    >
                                        Primary
                                    </button>
                                    <button
                                        onclick={() => assignSecondary(sid)}
                                        class="flex-1 text-xs py-1.5 rounded-lg transition-colors cursor-pointer
                                            {isSecondary
                                            ? 'bg-amber-600 text-white font-medium'
                                            : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}"
                                    >
                                        Secondary
                                    </button>
                                </div>
                            </div>
                        {/each}
                    </div>
                </div>
            {/if}

            {#if rtsList.length === 0 && activeSensors.length === 0}
                <div
                    class="bg-slate-800 rounded-xl border border-slate-700 p-8 text-center"
                >
                    <div class="text-3xl mb-2">🔄</div>
                    <p class="text-sm text-slate-500">
                        No sensors available. Add RTS stations or external
                        sensors first.
                    </p>
                </div>
            {/if}
        </div>

        <!-- ── Live Charts ────────────────────────────────── -->
        {#if stateHistory.length === 0}
            <div
                class="bg-slate-800 rounded-xl border border-slate-700 p-8 text-center"
            >
                <p class="text-sm text-slate-500">Waiting for state data…</p>
            </div>
        {:else}
            <div class="space-y-4">
                {#each stateFields as field, i (field)}
                    <div
                        class="bg-slate-800 rounded-xl border border-slate-700 p-5"
                    >
                        <div class="flex items-center justify-between mb-4">
                            <h3 class="font-semibold font-mono">{field}</h3>
                            <span class="text-xs text-slate-500">
                                Polling every 2 s &middot; {stateHistory.length}
                                points
                            </span>
                        </div>
                        <div class="relative h-52">
                            <canvas use:fieldChart={field}></canvas>
                        </div>
                    </div>
                {/each}
            </div>
        {/if}
    {/if}
</div>
