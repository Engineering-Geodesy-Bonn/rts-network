<script lang="ts">
    import { onMount, onDestroy, tick } from "svelte";
    import { Chart, registerables } from "chart.js";
    import { getCorrectedMeasurements, getRts } from "../api/client";
    import type { MeasurementResponse, RTSResponse } from "../api/types";
    import { JOB_TYPE_NAMES } from "../constants";

    Chart.register(...registerables);

    let {
        jobId,
        rtsId,
        jobType,
        onclose,
    }: {
        jobId: number;
        rtsId: number | null;
        jobType: string;
        onclose: () => void;
    } = $props();

    // ── Coordinate conversion ───────────────────────────────
    function computeX(
        stX: number,
        orient: number,
        m: MeasurementResponse,
    ): number {
        return (
            stX +
            m.distance *
                Math.sin(m.vertical_angle) *
                Math.sin(m.horizontal_angle + orient)
        );
    }

    function computeY(
        stY: number,
        orient: number,
        m: MeasurementResponse,
    ): number {
        return (
            stY +
            m.distance *
                Math.sin(m.vertical_angle) *
                Math.cos(m.horizontal_angle + orient)
        );
    }

    function computeZ(stZ: number, m: MeasurementResponse): number {
        return stZ + m.distance * Math.cos(m.vertical_angle);
    }

    // ── State ───────────────────────────────────────────────
    // svelte-ignore non_reactive_update
    let xyCanvas: HTMLCanvasElement;
    // svelte-ignore non_reactive_update
    let xCanvas: HTMLCanvasElement;
    // svelte-ignore non_reactive_update
    let yCanvas: HTMLCanvasElement;
    // svelte-ignore non_reactive_update
    let zCanvas: HTMLCanvasElement;
    let xyChart: Chart | null = null;
    let xChart: Chart | null = null;
    let yChart: Chart | null = null;
    let zChart: Chart | null = null;

    let loading = $state(true);
    let error = $state("");
    let measurements = $state<MeasurementResponse[]>([]);
    let rts = $state<RTSResponse | null>(null);

    // ── Chart styles ────────────────────────────────────────
    const lineColor = "#3b82f6";
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
            interaction: { mode: "index" as const, intersect: false },
            plugins: { legend: { display: false }, tooltip: tooltipStyle },
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

    function buildCharts() {
        if (!xyCanvas || measurements.length === 0) return;

        const stX = rts?.station_x ?? 0;
        const stY = rts?.station_y ?? 0;
        const stZ = rts?.station_z ?? 0;
        const orient = rts?.orientation ?? 0;

        const sorted = [...measurements].sort(
            (a, b) => a.controller_timestamp - b.controller_timestamp,
        );

        const xs = sorted.map((m) => computeX(stX, orient, m));
        const ys = sorted.map((m) => computeY(stY, orient, m));
        const zs = sorted.map((m) => computeZ(stZ, m));
        const labels = sorted.map((m) =>
            new Date(m.controller_timestamp * 1000).toLocaleTimeString(),
        );

        // 2D scatter
        xyChart?.destroy();
        xyChart = new Chart(xyCanvas, {
            type: "scatter",
            data: {
                datasets: [
                    {
                        label: "Position",
                        data: xs.map((x, i) => ({ x, y: ys[i] })),
                        borderColor: lineColor,
                        backgroundColor: lineColor + "40",
                        pointRadius: 1.5,
                        pointHoverRadius: 4,
                        showLine: true,
                        borderWidth: 1.5,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 1,
                animation: { duration: 0 },
                plugins: { legend: { display: false }, tooltip: tooltipStyle },
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

        // X over time
        xChart?.destroy();
        xChart = new Chart(xCanvas, {
            type: "line",
            data: {
                labels,
                datasets: [
                    {
                        label: "X",
                        data: xs,
                        borderColor: "#3b82f6",
                        backgroundColor: "#3b82f620",
                        borderWidth: 1.5,
                        pointRadius: 0,
                        tension: 0.2,
                    },
                ],
            },
            options: timeScaleOpts("X (m)"),
        });

        // Y over time
        yChart?.destroy();
        yChart = new Chart(yCanvas, {
            type: "line",
            data: {
                labels,
                datasets: [
                    {
                        label: "Y",
                        data: ys,
                        borderColor: "#22c55e",
                        backgroundColor: "#22c55e20",
                        borderWidth: 1.5,
                        pointRadius: 0,
                        tension: 0.2,
                    },
                ],
            },
            options: timeScaleOpts("Y (m)"),
        });

        // Z over time
        zChart?.destroy();
        zChart = new Chart(zCanvas, {
            type: "line",
            data: {
                labels,
                datasets: [
                    {
                        label: "Z",
                        data: zs,
                        borderColor: "#f59e0b",
                        backgroundColor: "#f59e0b20",
                        borderWidth: 1.5,
                        pointRadius: 0,
                        tension: 0.2,
                    },
                ],
            },
            options: timeScaleOpts("Z (m)"),
        });
    }

    async function loadAndPlot() {
        loading = true;
        error = "";
        try {
            const [meas, rtsData] = await Promise.all([
                getCorrectedMeasurements(jobId),
                rtsId != null ? getRts(rtsId) : Promise.resolve(null),
            ]);
            measurements = meas;
            rts = rtsData;
            loading = false;

            // Wait for Svelte to render the canvas elements
            await tick();
            await new Promise((r) => requestAnimationFrame(r));
            buildCharts();
        } catch (e: any) {
            error = e.message || "Failed to load measurements";
            loading = false;
        }
    }

    onMount(() => {
        loadAndPlot();
    });

    onDestroy(() => {
        xyChart?.destroy();
        xChart?.destroy();
        yChart?.destroy();
        zChart?.destroy();
    });
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
    class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4"
    onclick={onclose}
    onkeydown={(e) => e.key === "Escape" && onclose()}
    role="dialog"
    tabindex="-1"
>
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
        class="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-5xl max-h-[92vh] flex flex-col shadow-2xl"
        onclick={(e) => e.stopPropagation()}
        onkeydown={() => {}}
    >
        <!-- Header -->
        <div
            class="p-5 border-b border-slate-700 flex items-center justify-between shrink-0"
        >
            <div>
                <h2 class="text-lg font-semibold text-white">
                    {JOB_TYPE_NAMES[jobType] ?? jobType}
                    <span class="text-slate-400 text-sm font-normal"
                        >— Job #{jobId}</span
                    >
                </h2>
                <p class="text-xs text-slate-500 mt-0.5">
                    {measurements.length} corrected measurements
                    {#if rts}
                        &middot; {rts.name}
                    {/if}
                </p>
            </div>
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

        <!-- Content -->
        <div class="p-5 overflow-y-auto flex-1">
            {#if error}
                <div
                    class="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg mb-4 text-sm"
                >
                    {error}
                </div>
            {/if}

            {#if loading}
                <div class="flex items-center justify-center py-16">
                    <div
                        class="inline-block w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full animate-spin"
                    ></div>
                    <span class="ml-3 text-slate-400 text-sm"
                        >Loading corrected measurements...</span
                    >
                </div>
            {:else if measurements.length === 0}
                <div class="text-center py-12 text-slate-500">
                    No corrected measurements available for this job.
                </div>
            {:else}
                <!-- 2D Position -->
                <div class="mb-5">
                    <h3
                        class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2"
                    >
                        2D Position (X vs Y)
                    </h3>
                    <div
                        class="bg-slate-900 rounded-lg border border-slate-700 p-3"
                    >
                        <canvas bind:this={xyCanvas}></canvas>
                    </div>
                </div>

                <!-- X / Y / Z subplots -->
                <div class="grid gap-4 md:grid-cols-3">
                    <div>
                        <h3
                            class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2"
                        >
                            X over Time
                        </h3>
                        <div
                            class="bg-slate-900 rounded-lg border border-slate-700 p-3"
                            style="height: 200px;"
                        >
                            <canvas bind:this={xCanvas}></canvas>
                        </div>
                    </div>
                    <div>
                        <h3
                            class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2"
                        >
                            Y over Time
                        </h3>
                        <div
                            class="bg-slate-900 rounded-lg border border-slate-700 p-3"
                            style="height: 200px;"
                        >
                            <canvas bind:this={yCanvas}></canvas>
                        </div>
                    </div>
                    <div>
                        <h3
                            class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2"
                        >
                            Z over Time
                        </h3>
                        <div
                            class="bg-slate-900 rounded-lg border border-slate-700 p-3"
                            style="height: 200px;"
                        >
                            <canvas bind:this={zCanvas}></canvas>
                        </div>
                    </div>
                </div>
            {/if}
        </div>
    </div>
</div>
