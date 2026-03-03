<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import { Chart, registerables } from "chart.js";
    import { getLatestMeasurements, getAllRts } from "../api/client";
    import { measurementCache } from "../stores/measurements";
    import { currentSession } from "../stores/session";
    import type {
        MeasurementResponse,
        RTSResponse,
        SessionResponse,
    } from "../api/types";

    Chart.register(...registerables);

    let session = $state<SessionResponse | null>(null);

    const unsubSession = currentSession.subscribe((s) => {
        session = s;
    });

    // ── Coordinate conversion (mirrors old Python utils) ────
    function computeX(
        stationX: number,
        orientation: number,
        m: MeasurementResponse,
    ): number {
        return (
            stationX +
            m.distance *
                Math.sin(m.vertical_angle) *
                Math.sin(m.horizontal_angle + orientation)
        );
    }

    function computeY(
        stationY: number,
        orientation: number,
        m: MeasurementResponse,
    ): number {
        return (
            stationY +
            m.distance *
                Math.sin(m.vertical_angle) *
                Math.cos(m.horizontal_angle + orientation)
        );
    }

    function computeZ(stationZ: number, m: MeasurementResponse): number {
        return stationZ + m.distance * Math.cos(m.vertical_angle);
    }

    // ── State ───────────────────────────────────────────────
    let xyCanvas: HTMLCanvasElement;
    let xCanvas: HTMLCanvasElement;
    let yCanvas: HTMLCanvasElement;
    let zCanvas: HTMLCanvasElement;
    let xyChart: Chart | null = null;
    let xChart: Chart | null = null;
    let yChart: Chart | null = null;
    let zChart: Chart | null = null;
    let polling = $state(true);
    let pollInterval = $state(2000);
    let error = $state("");
    let measurementCount = $state(0);
    let lastFetch = $state("");
    let cached = $state<MeasurementResponse[]>([]);
    let rtsMap = $state<Record<number, RTSResponse>>({});
    let pollTimerId: ReturnType<typeof setInterval> | null = null;

    const unsub = measurementCache.subscribe((m) => {
        cached = m;
        measurementCount = m.length;
        updateCharts();
    });

    // ── Chart colours per RTS ───────────────────────────────
    const COLORS = [
        "#3b82f6",
        "#22c55e",
        "#f59e0b",
        "#ef4444",
        "#a855f7",
        "#06b6d4",
        "#ec4899",
        "#84cc16",
    ];
    function color(idx: number) {
        return COLORS[idx % COLORS.length];
    }

    // ── Shared chart options factory ────────────────────────
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

    function timeScaleOpts(axisLabel: string) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 0 } as const,
            interaction: {
                mode: "index" as const,
                intersect: false,
            },
            plugins: { legend: legendStyle, tooltip: tooltipStyle },
            scales: {
                x: {
                    ticks: { ...tickStyle, maxTicksLimit: 8 },
                    grid: darkGrid,
                },
                y: {
                    title: {
                        display: true,
                        text: axisLabel,
                        color: "#94a3b8",
                        font: { size: 11 },
                    },
                    ticks: tickStyle,
                    grid: darkGrid,
                },
            },
        };
    }

    // ── Build charts ────────────────────────────────────────
    function buildCharts() {
        // 2D position (scatter x vs y)
        if (xyCanvas) {
            xyChart?.destroy();
            xyChart = new Chart(xyCanvas, {
                type: "scatter",
                data: { datasets: [] },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    aspectRatio: 1,
                    animation: { duration: 0 },
                    plugins: { legend: legendStyle, tooltip: tooltipStyle },
                    scales: {
                        x: {
                            title: {
                                display: true,
                                text: "X (m)",
                                color: "#94a3b8",
                                font: { size: 11 },
                            },
                            ticks: tickStyle,
                            grid: darkGrid,
                        },
                        y: {
                            title: {
                                display: true,
                                text: "Y (m)",
                                color: "#94a3b8",
                                font: { size: 11 },
                            },
                            ticks: tickStyle,
                            grid: darkGrid,
                        },
                    },
                },
            });
        }

        // Time-series subplots
        if (xCanvas) {
            xChart?.destroy();
            xChart = new Chart(xCanvas, {
                type: "line",
                data: { labels: [], datasets: [] },
                options: timeScaleOpts("X (m)"),
            });
        }
        if (yCanvas) {
            yChart?.destroy();
            yChart = new Chart(yCanvas, {
                type: "line",
                data: { labels: [], datasets: [] },
                options: timeScaleOpts("Y (m)"),
            });
        }
        if (zCanvas) {
            zChart?.destroy();
            zChart = new Chart(zCanvas, {
                type: "line",
                data: { labels: [], datasets: [] },
                options: timeScaleOpts("Z (m)"),
            });
        }

        updateCharts();
    }

    function updateCharts() {
        if (!xyChart && !xChart) return;

        // Group measurements by rts_id
        const byRts = new Map<number, MeasurementResponse[]>();
        const sorted = [...cached].sort(
            (a, b) => a.controller_timestamp - b.controller_timestamp,
        );
        for (const m of sorted) {
            const key = m.rts_id ?? 0;
            if (!byRts.has(key)) byRts.set(key, []);
            byRts.get(key)!.push(m);
        }

        const rtsIds = [...byRts.keys()].sort();

        // 2D scatter: X vs Y
        if (xyChart) {
            xyChart.data.datasets = rtsIds.map((rtsId, ci) => {
                const rts = rtsMap[rtsId];
                const stX = rts?.station_x ?? 0;
                const stY = rts?.station_y ?? 0;
                const orient = rts?.orientation ?? 0;
                const pts = byRts.get(rtsId)!;
                return {
                    label: rts?.name ?? `RTS ${rtsId}`,
                    data: pts.map((m) => ({
                        x: computeX(stX, orient, m),
                        y: computeY(stY, orient, m),
                    })),
                    borderColor: color(ci),
                    backgroundColor: color(ci) + "40",
                    pointRadius: 2,
                    pointHoverRadius: 4,
                    showLine: true,
                    borderWidth: 1.5,
                    tension: 0,
                };
            });
            xyChart.update("none");
        }

        // Time-series labels from ALL sorted measurements
        const labels = sorted.map((m) =>
            new Date(m.controller_timestamp * 1000).toLocaleTimeString(),
        );

        // Build per-RTS time-series datasets aligned to global labels
        // Each dataset produces a value only for its own RTS measurements, null otherwise
        function makeDatasets(
            valueFn: (rtsId: number, m: MeasurementResponse) => number,
        ) {
            return rtsIds.map((rtsId, ci) => {
                const rts = rtsMap[rtsId];
                return {
                    label: rts?.name ?? `RTS ${rtsId}`,
                    data: sorted.map((m) =>
                        (m.rts_id ?? 0) === rtsId ? valueFn(rtsId, m) : null,
                    ),
                    borderColor: color(ci),
                    backgroundColor: color(ci) + "20",
                    borderWidth: 1.5,
                    pointRadius: 0,
                    tension: 0.2,
                    spanGaps: true,
                };
            });
        }

        function xVal(rtsId: number, m: MeasurementResponse) {
            const rts = rtsMap[rtsId];
            return computeX(rts?.station_x ?? 0, rts?.orientation ?? 0, m);
        }
        function yVal(rtsId: number, m: MeasurementResponse) {
            const rts = rtsMap[rtsId];
            return computeY(rts?.station_y ?? 0, rts?.orientation ?? 0, m);
        }
        function zVal(rtsId: number, m: MeasurementResponse) {
            const rts = rtsMap[rtsId];
            return computeZ(rts?.station_z ?? 0, m);
        }

        for (const [chart, fn] of [
            [xChart, xVal],
            [yChart, yVal],
            [zChart, zVal],
        ] as const) {
            if (!chart) continue;
            chart.data.labels = labels;
            chart.data.datasets = makeDatasets(fn);
            chart.update("none");
        }
    }

    // ── Polling ─────────────────────────────────────────────
    async function fetchLatest() {
        try {
            const measurements = await getLatestMeasurements();
            if (measurements.length > 0) {
                measurementCache.addMeasurements(measurements);
            }
            lastFetch = new Date().toLocaleTimeString();
            error = "";
        } catch (e: any) {
            error = e.message || "Failed to fetch measurements";
        }
    }

    function startPolling() {
        stopPolling();
        fetchLatest();
        pollTimerId = setInterval(fetchLatest, pollInterval);
    }

    function stopPolling() {
        if (pollTimerId) {
            clearInterval(pollTimerId);
            pollTimerId = null;
        }
    }

    function togglePolling() {
        polling = !polling;
        if (polling) startPolling();
        else stopPolling();
    }

    function handleIntervalChange(e: Event) {
        const target = e.target as HTMLSelectElement;
        pollInterval = parseInt(target.value, 10);
        if (polling) startPolling();
    }

    function clearCache() {
        measurementCache.clear();
    }

    async function loadRtsData() {
        try {
            if (!session) return;
            const all = await getAllRts(session.id);
            const map: Record<number, RTSResponse> = {};
            for (const r of all) map[r.id] = r;
            rtsMap = map;
        } catch {
            /* ignore – coordinates will default to 0 */
        }
    }

    onMount(async () => {
        await loadRtsData();
        buildCharts();
        if (polling) startPolling();
    });

    onDestroy(() => {
        stopPolling();
        xyChart?.destroy();
        xChart?.destroy();
        yChart?.destroy();
        zChart?.destroy();
        unsub();
        unsubSession();
    });
</script>

<div class="max-w-6xl mx-auto">
    <!-- Header -->
    <div class="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
            <h2 class="text-2xl font-bold">Live Measurements</h2>
            <p class="text-sm text-slate-400 mt-1">
                {measurementCount} cached &middot; Last fetch: {lastFetch ||
                    "never"}
            </p>
        </div>
        <div class="flex items-center gap-3">
            <div class="flex items-center gap-2">
                <label class="text-sm text-slate-400" for="poll-interval"
                    >Interval:</label
                >
                <select
                    id="poll-interval"
                    value={pollInterval}
                    onchange={handleIntervalChange}
                    class="bg-slate-800 border border-slate-600 rounded-lg px-2 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500"
                >
                    <option value={500}>0.5s</option>
                    <option value={1000}>1s</option>
                    <option value={2000}>2s</option>
                    <option value={5000}>5s</option>
                    <option value={10000}>10s</option>
                </select>
            </div>
            <button
                onclick={togglePolling}
                class="{polling
                    ? 'bg-amber-600 hover:bg-amber-700'
                    : 'bg-green-600 hover:bg-green-700'} text-white text-sm font-medium px-4 py-1.5 rounded-lg transition-colors cursor-pointer"
            >
                {polling ? "⏸ Pause" : "▶ Resume"}
            </button>
            <button
                onclick={clearCache}
                class="bg-slate-700 hover:bg-slate-600 text-white text-sm px-4 py-1.5 rounded-lg transition-colors cursor-pointer"
            >
                Clear
            </button>
        </div>
    </div>

    {#if error}
        <div
            class="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg mb-4 text-sm"
        >
            {error}
        </div>
    {/if}

    <!-- 2D Position Plot -->
    <div class="mb-4">
        <h3
            class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2"
        >
            2D Position (X vs Y)
        </h3>
        <div class="bg-slate-800 rounded-xl border border-slate-700 p-4">
            <canvas bind:this={xyCanvas}></canvas>
        </div>
    </div>

    <!-- X / Y / Z Subplots -->
    <div class="grid gap-4 md:grid-cols-3 mb-6">
        <div>
            <h3
                class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2"
            >
                X over Time
            </h3>
            <div
                class="bg-slate-800 rounded-xl border border-slate-700 p-3"
                style="height: 250px;"
            >
                <canvas bind:this={xCanvas}></canvas>
            </div>
        </div>
        <div>
            <h3
                class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2"
            >
                Y over Time
            </h3>
            <div
                class="bg-slate-800 rounded-xl border border-slate-700 p-3"
                style="height: 250px;"
            >
                <canvas bind:this={yCanvas}></canvas>
            </div>
        </div>
        <div>
            <h3
                class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2"
            >
                Z over Time
            </h3>
            <div
                class="bg-slate-800 rounded-xl border border-slate-700 p-3"
                style="height: 250px;"
            >
                <canvas bind:this={zCanvas}></canvas>
            </div>
        </div>
    </div>

    <!-- Measurement Table (latest 10) -->
    {#if cached.length > 0}
        <div
            class="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden"
        >
            <div
                class="p-4 border-b border-slate-700 flex items-center justify-between"
            >
                <h3 class="font-semibold">Recent Measurements</h3>
                <span class="text-xs text-slate-500">Showing latest 10</span>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead class="bg-slate-700/50 sticky top-0">
                        <tr>
                            <th
                                class="px-4 py-2 text-left text-slate-400 font-medium"
                                >Time</th
                            >
                            <th
                                class="px-4 py-2 text-left text-slate-400 font-medium"
                                >RTS</th
                            >
                            <th
                                class="px-4 py-2 text-right text-slate-400 font-medium"
                                >X (m)</th
                            >
                            <th
                                class="px-4 py-2 text-right text-slate-400 font-medium"
                                >Y (m)</th
                            >
                            <th
                                class="px-4 py-2 text-right text-slate-400 font-medium"
                                >Z (m)</th
                            >
                            <th
                                class="px-4 py-2 text-right text-slate-400 font-medium"
                                >Dist (m)</th
                            >
                            <th
                                class="px-4 py-2 text-right text-slate-400 font-medium"
                                >GRC</th
                            >
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-700/50">
                        {#each [...cached]
                            .reverse()
                            .slice(0, 10) as m, i (m.controller_timestamp + ":" + m.rts_id + ":" + i)}
                            {@const rts = rtsMap[m.rts_id ?? 0]}
                            {@const mx = computeX(
                                rts?.station_x ?? 0,
                                rts?.orientation ?? 0,
                                m,
                            )}
                            {@const my = computeY(
                                rts?.station_y ?? 0,
                                rts?.orientation ?? 0,
                                m,
                            )}
                            {@const mz = computeZ(rts?.station_z ?? 0, m)}
                            <tr class="hover:bg-slate-700/30">
                                <td
                                    class="px-4 py-1.5 text-slate-300 font-mono text-xs"
                                    >{new Date(
                                        m.controller_timestamp * 1000,
                                    ).toLocaleTimeString()}</td
                                >
                                <td class="px-4 py-1.5 text-slate-300"
                                    >{rts?.name ?? m.rts_id ?? "—"}</td
                                >
                                <td
                                    class="px-4 py-1.5 text-slate-300 text-right font-mono"
                                    >{mx.toFixed(4)}</td
                                >
                                <td
                                    class="px-4 py-1.5 text-slate-300 text-right font-mono"
                                    >{my.toFixed(4)}</td
                                >
                                <td
                                    class="px-4 py-1.5 text-slate-300 text-right font-mono"
                                    >{mz.toFixed(4)}</td
                                >
                                <td
                                    class="px-4 py-1.5 text-slate-300 text-right font-mono"
                                    >{m.distance.toFixed(4)}</td
                                >
                                <td
                                    class="px-4 py-1.5 text-right font-mono {m.geocom_return_code ===
                                    0
                                        ? 'text-green-400'
                                        : 'text-red-400'}"
                                    >{m.geocom_return_code}</td
                                >
                            </tr>
                        {/each}
                    </tbody>
                </table>
            </div>
        </div>
    {/if}
</div>
