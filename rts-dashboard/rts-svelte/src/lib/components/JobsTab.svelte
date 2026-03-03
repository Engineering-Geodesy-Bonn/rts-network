<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import {
        getAllJobs,
        getAllRts,
        deleteJob,
        updateJobStatus,
        downloadTrajectory,
        downloadRawMeasurements,
    } from "../api/client";
    import { currentSession } from "../stores/session";
    import type {
        RTSJobResponse,
        RTSResponse,
        SessionResponse,
    } from "../api/types";
    import {
        JOB_TYPE_NAMES,
        JOB_STATUS_COLORS,
        JOB_STATUS_BG_COLORS,
    } from "../constants";
    import JobPlotModal from "./JobPlotModal.svelte";

    // ── State ───────────────────────────────────────────────
    let jobs = $state<RTSJobResponse[]>([]);
    let rtsMap = $state<Record<number, RTSResponse>>({});
    let loading = $state(true);
    let error = $state("");
    let downloadingId = $state<number | null>(null);
    let downloadingAll = $state(false);
    let plottingJob = $state<RTSJobResponse | null>(null);
    let pollTimerId: ReturnType<typeof setInterval> | null = null;
    let session = $state<SessionResponse | null>(null);

    const unsub = currentSession.subscribe((s) => {
        session = s;
    });

    const HIDDEN_TYPES = new Set(["change_face", "turn_to_target"]);
    const DOWNLOADABLE_TYPES = new Set([
        "track_prism",
        "dummy_tracking",
        "static_measurement",
    ]);

    // ── Derived: group by date ──────────────────────────────
    let groupedJobs = $derived.by(() => {
        const filtered = jobs.filter((j) => !HIDDEN_TYPES.has(j.job_type));
        const groups = new Map<string, RTSJobResponse[]>();
        for (const job of filtered) {
            const date = new Date(job.created_at * 1000).toLocaleDateString();
            if (!groups.has(date)) groups.set(date, []);
            groups.get(date)!.push(job);
        }
        // Sort dates descending (newest first)
        return [...groups.entries()].sort(
            (a, b) => new Date(b[0]).getTime() - new Date(a[0]).getTime(),
        );
    });

    // ── Data Loading ────────────────────────────────────────
    async function loadData() {
        loading = true;
        error = "";
        try {
            if (!session) return;
            const [allJobs, allRts] = await Promise.all([
                getAllJobs(),
                getAllRts(session.id),
            ]);
            // Filter jobs to only those belonging to session RTS
            const rtsIds = new Set(allRts.map((r) => r.id));
            jobs = allJobs.filter(
                (j) => j.rts_id != null && rtsIds.has(j.rts_id),
            );
            const map: Record<number, RTSResponse> = {};
            for (const r of allRts) map[r.id] = r;
            rtsMap = map;
        } catch (e: any) {
            error = e.message || "Failed to load jobs";
        } finally {
            loading = false;
        }
    }

    function startPolling() {
        stopPolling();
        pollTimerId = setInterval(loadData, 5000);
    }

    function stopPolling() {
        if (pollTimerId) {
            clearInterval(pollTimerId);
            pollTimerId = null;
        }
    }

    // ── Actions ─────────────────────────────────────────────
    async function handleStop(jobId: number) {
        try {
            await updateJobStatus(jobId, "finished");
            await loadData();
        } catch (e: any) {
            error = e.message || "Failed to stop job";
        }
    }

    async function handleStopAll() {
        error = "";
        try {
            const running = jobs.filter(
                (j) => j.job_status === "running" || j.job_status === "pending",
            );
            await Promise.allSettled(
                running.map((j) => updateJobStatus(j.job_id, "finished")),
            );
            await loadData();
        } catch (e: any) {
            error = e.message || "Failed to stop all jobs";
        }
    }

    async function handleDelete(jobId: number) {
        if (!confirm(`Delete job #${jobId}?`)) return;
        try {
            await deleteJob(jobId);
            jobs = jobs.filter((j) => j.job_id !== jobId);
        } catch (e: any) {
            error = e.message || "Failed to delete job";
        }
    }

    async function handleDownloadRaw(jobId: number) {
        downloadingId = jobId;
        try {
            await downloadRawMeasurements(jobId);
        } catch (e: any) {
            error = e.message || "Download failed";
        } finally {
            downloadingId = null;
        }
    }

    async function handleDownloadTrajectory(jobId: number) {
        downloadingId = jobId;
        try {
            await downloadTrajectory(jobId);
        } catch (e: any) {
            error = e.message || "Download failed";
        } finally {
            downloadingId = null;
        }
    }

    async function handleDownloadAllTrajectories() {
        downloadingAll = true;
        error = "";
        try {
            const trajectoryJobs = jobs.filter(
                (j) =>
                    (j.job_type === "track_prism" ||
                        j.job_type === "dummy_tracking") &&
                    (j.num_measurements ?? 0) > 0,
            );
            if (trajectoryJobs.length === 0) {
                error = "No trajectory jobs to download.";
                return;
            }
            for (const job of trajectoryJobs) {
                await downloadTrajectory(job.job_id);
            }
        } catch (e: any) {
            error = e.message || "Failed to download all trajectories";
        } finally {
            downloadingAll = false;
        }
    }

    // ── Helpers ──────────────────────────────────────────────
    function formatTimestamp(ts: number | null): string {
        if (!ts) return "—";
        return new Date(ts * 1000).toLocaleString();
    }

    function formatDuration(seconds: number | null): string {
        if (!seconds || seconds <= 0) return "—";
        const m = Math.floor(seconds / 60);
        const s = Math.round(seconds % 60);
        return `${m}:${s.toString().padStart(2, "0")}`;
    }

    function rtsName(rtsId: number | null): string {
        if (rtsId == null) return "—";
        return rtsMap[rtsId]?.name ?? `RTS ${rtsId}`;
    }

    let visibleCount = $derived(
        jobs.filter((j) => !HIDDEN_TYPES.has(j.job_type)).length,
    );

    let runningCount = $derived(
        jobs.filter(
            (j) => j.job_status === "running" || j.job_status === "pending",
        ).length,
    );

    onMount(async () => {
        await loadData();
        startPolling();
    });

    onDestroy(() => {
        stopPolling();
        unsub();
    });
</script>

<div class="max-w-6xl mx-auto">
    <!-- Header -->
    <div class="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
            <h2 class="text-2xl font-bold">Jobs</h2>
            <p class="text-sm text-slate-400 mt-1">
                {visibleCount} total
                {#if runningCount > 0}
                    &middot; <span class="text-blue-400"
                        >{runningCount} active</span
                    >
                {/if}
            </p>
        </div>
        <div class="flex flex-wrap gap-2">
            {#if runningCount > 0}
                <button
                    onclick={handleStopAll}
                    class="bg-red-600 hover:bg-red-700 text-white font-medium px-4 py-2 rounded-lg transition-colors text-sm cursor-pointer"
                >
                    ■ Stop All
                </button>
            {/if}
            <button
                onclick={handleDownloadAllTrajectories}
                disabled={downloadingAll}
                class="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium px-4 py-2 rounded-lg transition-colors text-sm cursor-pointer"
            >
                {downloadingAll
                    ? "⏳ Downloading..."
                    : "📈 Download All Trajectories"}
            </button>
            <button
                onclick={loadData}
                class="text-slate-400 hover:text-white hover:bg-slate-700 px-3 py-2 rounded-lg transition-colors text-sm cursor-pointer"
            >
                ↻ Refresh
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

    {#if loading && jobs.length === 0}
        <div class="flex items-center justify-center py-12">
            <div
                class="inline-block w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full animate-spin"
            ></div>
        </div>
    {:else if jobs.length === 0}
        <div
            class="bg-slate-800 rounded-xl border border-slate-700 p-12 text-center"
        >
            <div class="text-4xl mb-3">📋</div>
            <h3 class="text-lg font-medium text-slate-300 mb-1">No jobs yet</h3>
            <p class="text-slate-500">
                Start tracking on the RTS tab to create jobs.
            </p>
        </div>
    {:else}
        <!-- Grouped by date -->
        {#each groupedJobs as [date, dateJobs] (date)}
            <div class="mb-6">
                <h3
                    class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-2"
                >
                    <span class="bg-slate-700 px-3 py-1 rounded-full"
                        >{date}</span
                    >
                    <span class="text-slate-600"
                        >{dateJobs.length} job{dateJobs.length !== 1
                            ? "s"
                            : ""}</span
                    >
                </h3>
                <div class="space-y-3">
                    {#each dateJobs as job (job.job_id)}
                        {@const canDownload =
                            DOWNLOADABLE_TYPES.has(job.job_type) &&
                            (job.num_measurements ?? 0) > 0}
                        {@const canTrajectory =
                            (job.job_type === "track_prism" ||
                                job.job_type === "dummy_tracking") &&
                            (job.num_measurements ?? 0) > 0}
                        {@const isRunning =
                            job.job_status === "running" ||
                            job.job_status === "pending"}
                        <div
                            class="bg-slate-800 rounded-xl border transition-colors
                                {isRunning
                                ? 'border-blue-500/40'
                                : 'border-slate-700'}"
                        >
                            <div
                                class="p-4 flex flex-col md:flex-row md:items-center gap-4"
                            >
                                <!-- Left: job info -->
                                <div class="flex-1 min-w-0">
                                    <div class="flex items-center gap-2 mb-1.5">
                                        <span class="font-semibold text-white">
                                            {JOB_TYPE_NAMES[job.job_type] ??
                                                job.job_type}
                                        </span>
                                        <span
                                            class="text-xs px-2 py-0.5 rounded-full border font-medium
                                                {JOB_STATUS_BG_COLORS[
                                                job.job_status
                                            ] ?? ''} {JOB_STATUS_COLORS[
                                                job.job_status
                                            ] ?? 'text-slate-400'}"
                                        >
                                            {job.job_status}
                                        </span>
                                        <span
                                            class="text-xs text-slate-600 font-mono"
                                            >#{job.job_id}</span
                                        >
                                    </div>
                                    <div
                                        class="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-1 text-xs"
                                    >
                                        <div>
                                            <span class="text-slate-500"
                                                >RTS:</span
                                            >
                                            <span class="text-slate-300 ml-1"
                                                >{rtsName(job.rts_id)}</span
                                            >
                                        </div>
                                        <div>
                                            <span class="text-slate-500"
                                                >Created:</span
                                            >
                                            <span class="text-slate-300 ml-1"
                                                >{formatTimestamp(
                                                    job.created_at,
                                                )}</span
                                            >
                                        </div>
                                        <div>
                                            <span class="text-slate-500"
                                                >Duration:</span
                                            >
                                            <span class="text-slate-300 ml-1"
                                                >{formatDuration(
                                                    job.duration,
                                                )}</span
                                            >
                                        </div>
                                        <div>
                                            <span class="text-slate-500"
                                                >Measurements:</span
                                            >
                                            <span class="text-slate-300 ml-1">
                                                {job.num_measurements ?? "—"}
                                                {#if job.datarate}
                                                    <span class="text-slate-500"
                                                        >({job.datarate.toFixed(
                                                            1,
                                                        )} Hz)</span
                                                    >
                                                {/if}
                                            </span>
                                        </div>
                                    </div>
                                </div>

                                <!-- Right: actions -->
                                <div class="flex flex-wrap gap-1.5 shrink-0">
                                    {#if isRunning}
                                        <button
                                            onclick={() =>
                                                handleStop(job.job_id)}
                                            class="bg-red-600 hover:bg-red-700 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
                                        >
                                            ■ Stop
                                        </button>
                                    {/if}

                                    {#if canDownload}
                                        <button
                                            onclick={() => (plottingJob = job)}
                                            class="bg-purple-600 hover:bg-purple-700 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
                                            title="Plot corrected measurements"
                                        >
                                            📊 Plot
                                        </button>
                                    {/if}

                                    {#if canTrajectory}
                                        <button
                                            onclick={() =>
                                                handleDownloadTrajectory(
                                                    job.job_id,
                                                )}
                                            disabled={downloadingId ===
                                                job.job_id}
                                            class="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
                                            title="Download trajectory (XYZ CSV)"
                                        >
                                            📈 Trajectory
                                        </button>
                                    {/if}

                                    {#if canDownload}
                                        <button
                                            onclick={() =>
                                                handleDownloadRaw(job.job_id)}
                                            disabled={downloadingId ===
                                                job.job_id}
                                            class="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
                                            title="Download raw measurements CSV"
                                        >
                                            📄 Raw
                                        </button>
                                    {/if}

                                    <button
                                        onclick={() => handleDelete(job.job_id)}
                                        class="text-slate-500 hover:text-red-400 hover:bg-red-500/10 text-xs px-2 py-1.5 rounded-lg transition-colors cursor-pointer"
                                        title="Delete job"
                                    >
                                        🗑️
                                    </button>
                                </div>
                            </div>
                        </div>
                    {/each}
                </div>
            </div>
        {/each}
    {/if}
</div>

{#if plottingJob}
    <JobPlotModal
        jobId={plottingJob.job_id}
        rtsId={plottingJob.rts_id}
        jobType={plottingJob.job_type}
        onclose={() => (plottingJob = null)}
    />
{/if}
