<script lang="ts">
    import { onMount, onDestroy, tick } from "svelte";
    import { createJob, getStatusBoard } from "../api/client";
    import { currentSession } from "../stores/session";
    import type {
        CheckStatus,
        DeviceBoardEntry,
        SessionResponse,
        StatusBoardResponse,
        StatusCheck,
        WorkerBoardEntry,
    } from "../api/types";
    import { JOB_TYPE_NAMES, STATUS_BOARD_POLL_MS } from "../constants";
    import {
        CHRONY_MODES,
        CHRONY_STATES,
        GPS_MODES,
        STATUS_BORDER,
        STATUS_LABEL,
        STATUS_PILL,
        STATUS_TEXT,
        fmtBytes,
        fmtDuration,
        fmtNumber,
        fmtSignedTime,
        fmtTime,
        worst,
    } from "../status";
    import CheckList from "./status/CheckList.svelte";
    import NetworkMap from "./status/NetworkMap.svelte";

    let session = $state<SessionResponse | null>(null);
    let board = $state<StatusBoardResponse | null>(null);
    let error = $state("");
    let notice = $state("");
    let lastSuccess = $state<number | null>(null);
    let rtt = $state<number | null>(null);
    let now = $state(Date.now());
    let selected = $state<string | null>(null);
    let expanded = $state<Record<string, boolean>>({});
    let checkingInstruments = $state(false);
    let pollTimer: ReturnType<typeof setTimeout> | null = null;
    let tickTimer: ReturnType<typeof setInterval> | null = null;
    let destroyed = false;

    const unsub = currentSession.subscribe((s) => (session = s));

    async function poll() {
        if (!session) return;
        const started = performance.now();
        try {
            board = await getStatusBoard(session.id);
            rtt = (performance.now() - started) / 1000;
            lastSuccess = Date.now();
            error = "";
        } catch (e: any) {
            error = e.message || "Failed to load status";
        } finally {
            if (!destroyed) pollTimer = setTimeout(poll, STATUS_BOARD_POLL_MS);
        }
    }

    onMount(() => {
        poll();
        tickTimer = setInterval(() => (now = Date.now()), 500);
    });

    onDestroy(() => {
        destroyed = true;
        unsub();
        if (pollTimer) clearTimeout(pollTimer);
        if (tickTimer) clearInterval(tickTimer);
    });

    // A board that is not refreshed must never look "ok"
    let updateAge = $derived(lastSuccess ? (now - lastSuccess) / 1000 : null);
    let stale = $derived(updateAge == null || updateAge > (3 * STATUS_BOARD_POLL_MS) / 1000);

    let connectionCheck = $derived<StatusCheck>(
        stale
            ? {
                  key: "dashboard",
                  label: "Dashboard ↔ API",
                  status: "fail",
                  message: lastSuccess
                      ? `No update for ${fmtDuration(updateAge)}${error ? ": " + error : ""}`
                      : error || "Connecting…",
              }
            : {
                  key: "dashboard",
                  label: "Dashboard ↔ API",
                  status: "ok",
                  message: `Updated ${fmtDuration(updateAge)} ago, request took ${fmtTime(rtt)}`,
              },
    );

    let browserClockCheck = $derived<StatusCheck | null>(
        board && rtt != null && lastSuccess
            ? {
                  key: "browser_clock",
                  label: "Browser clock",
                  status: "info",
                  message: `This browser is ${fmtSignedTime(lastSuccess / 1000 - rtt / 2 - board.server_time)} off the API server (ages are computed by the server)`,
              }
            : null,
    );

    let networkChecks = $derived<StatusCheck[]>([
        connectionCheck,
        ...(board?.network_checks ?? []),
        ...(browserClockCheck ? [browserClockCheck] : []),
    ]);

    let overall = $derived<CheckStatus>(
        stale || !board ? "fail" : worst([board.overall, connectionCheck.status]),
    );

    let problemCount = $derived(
        board ? board.counts.fail + board.counts.warn + board.counts.unknown : 0,
    );

    let sessionDevices = $derived(board?.devices.filter((d) => d.in_session) ?? []);
    let otherDevices = $derived(board?.devices.filter((d) => !d.in_session) ?? []);

    function rtsName(id: string | null): string {
        if (!id) return "–";
        return board?.rts.find((r) => r.rts_id === id)?.name ?? id.slice(0, 8);
    }

    function isExpanded(id: string, status: CheckStatus): boolean {
        return expanded[id] ?? status !== "ok";
    }

    function toggle(id: string, status: CheckStatus) {
        expanded = { ...expanded, [id]: !isExpanded(id, status) };
    }

    async function select(id: string) {
        selected = id;
        if (id.startsWith("device-")) expanded = { ...expanded, [id]: true };
        await tick();
        document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    async function runInstrumentChecks() {
        if (!board) return;
        const idle = board.rts.filter((r) => r.state === "idle");
        const busy = board.rts.length - idle.length;
        checkingInstruments = true;
        notice = "";
        try {
            const results = await Promise.allSettled(
                idle.map((r) => createJob({ rts_id: r.rts_id, job_type: "health_check" })),
            );
            const failed = results.filter((r) => r.status === "rejected").length;
            notice =
                `Instrument check started on ${idle.length - failed} RTS` +
                (busy ? ` (${busy} busy RTS skipped, their live data is checked instead)` : "") +
                (failed ? `, ${failed} could not be started` : "");
        } finally {
            checkingInstruments = false;
        }
    }

    function workerAge(w: WorkerBoardEntry, ts: number | null): number | null {
        // worker timestamps are compared with the worker's own clock
        return ts ? w.heartbeat.sent_at - ts : null;
    }

    function maxError(d: DeviceBoardEntry): number | null {
        const t = d.chrony?.tracking;
        return t ? Math.abs(t.system_time_offset) + t.root_dispersion + t.root_delay / 2 : null;
    }
</script>

{#snippet pill(status: CheckStatus, text?: string)}
    <span
        class="text-xs font-medium px-2 py-0.5 rounded-full border whitespace-nowrap {STATUS_PILL[
            status
        ]}">{text ?? STATUS_LABEL[status]}</span
    >
{/snippet}

{#snippet kv(rows: [string, string | number | null | undefined][])}
    <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
        {#each rows as [k, v] (k)}
            <dt class="text-slate-500">{k}</dt>
            <dd class="text-slate-200 font-mono break-all">{v ?? "–"}</dd>
        {/each}
    </dl>
{/snippet}

{#snippet section(title: string)}
    <h4 class="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
        {title}
    </h4>
{/snippet}

{#snippet deviceCard(d: DeviceBoardEntry)}
    {@const id = `device-${d.device_id}`}
    {@const open = isExpanded(id, d.status)}
    <div
        {id}
        class="bg-slate-800 rounded-xl border scroll-mt-4 {d.in_session
            ? STATUS_BORDER[d.status]
            : 'border-slate-700'} {selected === id ? 'ring-2 ring-blue-500/60' : ''}"
    >
        <button
            class="w-full flex flex-wrap items-center justify-between gap-2 p-4 text-left cursor-pointer"
            onclick={() => toggle(id, d.status)}
        >
            <div class="min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                    <span class="text-base font-semibold text-white">🖥 {d.hostname ?? d.ip}</span>
                    {#if !d.in_session}
                        <span class="text-xs text-slate-500">(not used in this session)</span>
                    {/if}
                </div>
                <div class="text-xs text-slate-400 font-mono mt-0.5">
                    {d.ip} · {d.workers.filter((w) => w.online).length} worker(s) ·
                    {d.rts_ids.map((r) => rtsName(r)).join(", ") || "no RTS"}
                </div>
            </div>
            <div class="flex items-center gap-2">
                {@render pill(d.in_session ? d.status : "info", d.in_session ? undefined : "Unused")}
                <span class="text-slate-500 text-sm">{open ? "▾" : "▸"}</span>
            </div>
        </button>
        {#if open}
            <div class="px-4 pb-4 space-y-4">
                <CheckList checks={d.checks} />

                {#if d.reports_health}
                    <div class="grid gap-4 lg:grid-cols-2">
                        <!-- Time sync -->
                        <div class="bg-slate-900/50 rounded-lg p-3">
                            {@render section("Clock synchronization (chrony)")}
                            {#if d.chrony?.tracking}
                                {@const t = d.chrony.tracking}
                                {@render kv([
                                    ["Reference", `${t.reference_name} (${t.reference_id})`],
                                    ["Stratum", t.stratum],
                                    ["Leap status", t.leap_status],
                                    ["System offset", fmtSignedTime(t.system_time_offset)],
                                    ["Last offset", fmtSignedTime(t.last_offset)],
                                    ["RMS offset", fmtTime(t.rms_offset)],
                                    ["Est. max error", fmtTime(maxError(d))],
                                    ["Root delay / dispersion", `${fmtTime(t.root_delay)} / ${fmtTime(t.root_dispersion)}`],
                                    ["Frequency", `${t.frequency_ppm.toFixed(3)} ppm (residual ${t.residual_freq_ppm.toFixed(3)}, skew ${t.skew_ppm.toFixed(3)})`],
                                    ["Update interval", `${t.update_interval.toFixed(1)} s`],
                                    ["vs. API server", d.clock ? `${fmtSignedTime(-d.clock.offset)} (±${fmtTime(d.clock.delay / 2)}, best of ${d.clock.samples})` : null],
                                ])}
                                {#if d.chrony.sources.length}
                                    <div class="overflow-x-auto mt-3">
                                        <table class="w-full text-xs font-mono">
                                            <thead class="text-slate-500 text-left">
                                                <tr>
                                                    <th class="pr-2 font-normal">Source</th>
                                                    <th class="pr-2 font-normal">State</th>
                                                    <th class="pr-2 font-normal">Reach</th>
                                                    <th class="pr-2 font-normal">Last</th>
                                                    <th class="pr-2 font-normal text-right">Offset</th>
                                                    <th class="font-normal text-right">Error</th>
                                                </tr>
                                            </thead>
                                            <tbody class="text-slate-300">
                                                {#each d.chrony.sources as s (s.name)}
                                                    <tr class={s.state === "*" ? "text-green-400" : ""}>
                                                        <td class="pr-2 py-0.5 whitespace-nowrap">{s.mode} {s.name} <span class="text-slate-500">{CHRONY_MODES[s.mode] ?? ""}</span></td>
                                                        <td class="pr-2 whitespace-nowrap">{s.state} {CHRONY_STATES[s.state] ?? ""}</td>
                                                        <td class="pr-2">{s.reach.toString(8)}</td>
                                                        <td class="pr-2">{s.last_rx != null ? `${s.last_rx} s` : "–"}</td>
                                                        <td class="pr-2 text-right whitespace-nowrap">{fmtSignedTime(s.offset)}</td>
                                                        <td class="text-right whitespace-nowrap">±{fmtTime(s.error)}</td>
                                                    </tr>
                                                {/each}
                                            </tbody>
                                        </table>
                                    </div>
                                {/if}
                            {:else}
                                <p class="text-xs text-slate-400">{d.chrony?.error ?? "No data"}</p>
                            {/if}
                        </div>

                        <!-- GNSS -->
                        <div class="bg-slate-900/50 rounded-lg p-3">
                            {@render section("GNSS receiver (gpsd)")}
                            {#if d.gps?.available}
                                {@const g = d.gps}
                                {@render kv([
                                    ["Fix", GPS_MODES[g.mode ?? 0] ?? String(g.mode)],
                                    ["Satellites", `${g.satellites_used ?? "?"} used / ${g.satellites_visible ?? "?"} visible`],
                                    ["DOP (H / P / T)", `${fmtNumber(g.hdop)} / ${fmtNumber(g.pdop)} / ${fmtNumber(g.tdop)}`],
                                    ["GNSS time", g.time],
                                    ["Position", g.lat != null && g.lon != null ? `${g.lat.toFixed(7)}°, ${g.lon.toFixed(7)}°, ${fmtNumber(g.alt, 1, "m")}` : null],
                                    ["Accuracy (h / v)", `${fmtNumber(g.eph, 1, "m")} / ${fmtNumber(g.epv, 1, "m")}`],
                                    ["Time error (ept)", g.ept != null ? fmtTime(g.ept) : null],
                                    ["Devices", g.devices.map((x) => `${x.path} (${x.driver})`).join(", ")],
                                ])}
                            {:else}
                                <p class="text-xs text-amber-400">{d.gps?.error ?? "No data"}</p>
                            {/if}
                        </div>

                        <!-- System -->
                        {#if d.system}
                            {@const s = d.system}
                            <div class="bg-slate-900/50 rounded-lg p-3">
                                {@render section("System")}
                                {@render kv([
                                    ["Hostname", s.hostname],
                                    ["Platform", s.platform],
                                    ["Python", s.python_version],
                                    ["Uptime", fmtDuration(s.uptime)],
                                    ["CPU temperature", s.cpu_temperature != null ? `${s.cpu_temperature.toFixed(1)} °C` : null],
                                    ["Load (1/5/15 min)", s.load_average.length ? `${s.load_average.map((l) => l.toFixed(2)).join(" / ")} (${s.cpu_count ?? "?"} CPUs)` : null],
                                    ["Memory available", s.memory_total ? `${fmtBytes(s.memory_available)} of ${fmtBytes(s.memory_total)}` : null],
                                    ["Disk free (log)", s.disk_total ? `${fmtBytes(s.disk_free)} of ${fmtBytes(s.disk_total)}` : null],
                                    ["Under-voltage", s.undervoltage == null ? "n/a" : s.undervoltage ? "YES" : "no"],
                                    ["PPS devices", s.pps_devices.join(", ") || "none"],
                                ])}
                            </div>
                            <div class="bg-slate-900/50 rounded-lg p-3">
                                {@render section("Serial ports")}
                                {#if s.serial_ports.length}
                                    <ul class="text-xs font-mono space-y-0.5 text-slate-300">
                                        {#each s.serial_ports as p (p.path)}
                                            <li class="break-all">
                                                {p.path}{#if p.target !== p.path}<span class="text-slate-500"> → {p.target}</span>{/if}
                                            </li>
                                        {/each}
                                    </ul>
                                {:else}
                                    <p class="text-xs text-slate-400">No serial ports found</p>
                                {/if}
                            </div>
                        {/if}
                    </div>

                    <!-- Workers -->
                    <div>
                        {@render section(`Workers (${d.workers.length})`)}
                        <div class="grid gap-3 md:grid-cols-2">
                            {#each d.workers as w (w.worker_id)}
                                {@const r = w.heartbeat.runtime}
                                <div class="bg-slate-900/50 rounded-lg p-3 border {STATUS_BORDER[w.status]}">
                                    <div class="flex items-center justify-between gap-2 mb-2">
                                        <span class="font-mono text-sm text-slate-200"
                                            >Worker {w.worker_id.slice(0, 8)}</span
                                        >
                                        {@render pill(w.status, w.online ? (r.state === "busy" ? "Busy" : "Idle") : "Offline")}
                                    </div>
                                    <CheckList checks={w.checks} />
                                    <div class="mt-2">
                                        {@render kv([
                                            ["Version", w.heartbeat.version],
                                            ["Running since", fmtDuration(workerAge(w, w.heartbeat.started_at))],
                                            ["Last heartbeat", `${fmtDuration(w.age)} ago`],
                                            ["Job", r.job_type ? `${JOB_TYPE_NAMES[r.job_type] ?? r.job_type} on ${rtsName(r.rts_id)} (${fmtDuration(workerAge(w, r.job_started_at))})` : "–"],
                                            ["Measurements", r.streaming ? `${r.measurements_sent} sent / ${r.measurements_logged} logged, backlog ${r.stream_backlog}` : "–"],
                                            ["Jobs done / failed", `${r.jobs_finished} / ${r.jobs_failed}`],
                                            ["Last error", r.last_error ? `${fmtDuration(workerAge(w, r.last_error_at))} ago: ${r.last_error}` : "none"],
                                            ["API target", w.heartbeat.api_host],
                                        ])}
                                    </div>
                                </div>
                            {/each}
                        </div>
                    </div>
                {/if}
            </div>
        {/if}
    </div>
{/snippet}

<div class="max-w-7xl mx-auto space-y-4 sm:space-y-6">
    <!-- Header -->
    <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
            <h2 class="text-xl sm:text-2xl font-bold">Network Status</h2>
            <p class="text-sm text-slate-400 mt-1">
                Live health of all devices, workers, instruments and clocks
                {#if lastSuccess}
                    · updated {fmtDuration(updateAge)} ago
                {/if}
            </p>
        </div>
        <button
            onclick={runInstrumentChecks}
            disabled={!board || checkingInstruments || board.rts.length === 0}
            class="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2.5 sm:py-2 rounded-lg transition-colors cursor-pointer"
            title="Reads battery, temperature and identification of all idle total stations and measures the serial latency"
        >
            🩺 Check instruments
        </button>
    </div>

    {#if notice}
        <div class="bg-blue-500/10 border border-blue-500/30 text-blue-300 px-4 py-3 rounded-lg text-sm">
            {notice}
            <button onclick={() => (notice = "")} class="ml-2 underline cursor-pointer">dismiss</button>
        </div>
    {/if}

    <!-- Overall banner -->
    <div class="rounded-xl border px-4 sm:px-6 py-4 sm:py-5 flex flex-wrap items-center gap-4 {STATUS_PILL[overall]}">
        <div class="text-3xl sm:text-4xl font-bold leading-none">
            {overall === "ok" ? "✓" : overall === "fail" ? "✕" : "!"}
        </div>
        <div class="flex-1 min-w-0">
            <div class="text-lg sm:text-xl font-semibold">
                {#if !board}
                    {error ? "API not reachable" : "Loading status…"}
                {:else if stale}
                    Status outdated – no connection to the API
                {:else if overall === "ok"}
                    All checks passed – the network is working and synchronized
                {:else if overall === "fail"}
                    {board.counts.fail} check(s) failed
                {:else}
                    {problemCount} check(s) need attention
                {/if}
            </div>
            {#if board}
                <div class="text-sm opacity-80 mt-0.5">
                    {board.counts.ok} ok · {board.counts.warn} warnings · {board.counts.fail} failures ·
                    {board.counts.unknown} unverified · {sessionDevices.length} device(s) · {board.rts.length} RTS
                </div>
            {/if}
        </div>
    </div>

    {#if board}
        <!-- Network map -->
        <div class="bg-slate-800 rounded-xl border border-slate-700 p-3 sm:p-4">
            <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
                <h3 class="font-semibold">Network map</h3>
                <span class="text-xs text-slate-500">Δ = device clock vs. API server · click a node for details</span>
            </div>
            <NetworkMap
                {board}
                apiStatus={stale ? "fail" : "ok"}
                dashboardRtt={rtt}
                {selected}
                onselect={select}
            />
        </div>

        <!-- Network checks -->
        <div class="bg-slate-800 rounded-xl border p-4 {STATUS_BORDER[worst(networkChecks.map((c) => c.status))]}">
            <h3 class="font-semibold mb-2">Network</h3>
            <CheckList checks={networkChecks} />
        </div>

        <!-- RTS -->
        <div>
            <h3 class="font-semibold mb-3">Total stations</h3>
            {#if board.rts.length === 0}
                <div class="bg-slate-800 rounded-xl border border-slate-700 p-6 text-center text-slate-400">
                    No RTS configured in this session.
                </div>
            {:else}
                <div class="grid gap-3 sm:gap-4 xl:grid-cols-2">
                    {#each board.rts as r (r.rts_id)}
                        {@const id = `rts-${r.rts_id}`}
                        {@const inst = r.instrument}
                        {@const tq = r.tracking}
                        <div
                            {id}
                            class="bg-slate-800 rounded-xl border p-4 scroll-mt-4 {STATUS_BORDER[r.status]} {selected === id ? 'ring-2 ring-blue-500/60' : ''}"
                        >
                            <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
                                <div class="min-w-0">
                                    <div class="text-base font-semibold text-white">📡 {r.name}</div>
                                    <div class="text-xs text-slate-400 font-mono mt-0.5 break-all">
                                        {r.device_ip ?? "?"} · {r.port} · {r.baudrate} baud
                                    </div>
                                </div>
                                <div class="flex items-center gap-2">
                                    <span class="text-xs text-slate-400">
                                        {r.state === "running" && r.running_job
                                            ? (JOB_TYPE_NAMES[r.running_job.job_type] ?? r.running_job.job_type)
                                            : r.state === "pending"
                                              ? "Pending"
                                              : "Idle"}
                                    </span>
                                    {@render pill(r.status)}
                                </div>
                            </div>
                            <CheckList checks={r.checks} />
                            <div class="grid gap-3 sm:grid-cols-2 mt-3">
                                <div class="bg-slate-900/50 rounded-lg p-3">
                                    {@render section("Instrument")}
                                    {#if inst}
                                        {@render kv([
                                            ["Model", inst.instrument_name],
                                            ["Serial number", inst.serial_number],
                                            ["Firmware", inst.software_version],
                                            ["Battery", inst.battery_capacity != null ? `${inst.battery_capacity} % (${(inst.power_source ?? "?").replace(/_/g, " ")})` : null],
                                            ["Temperature", inst.internal_temperature != null ? `${inst.internal_temperature.toFixed(1)} °C` : null],
                                            ["Face", inst.face != null ? (inst.face === 0 ? "I" : "II") : null],
                                            ["GeoCOM latency", inst.latency_mean != null ? `${fmtTime(inst.latency_mean)} (max ${fmtTime(inst.latency_max)}, n=${inst.latency_samples})` : null],
                                            ["Reported", `${fmtDuration(board.server_time - inst.received_at)} ago (${inst.source.replace(/_/g, " ")})`],
                                        ])}
                                        {#if inst.errors.length}
                                            <ul class="mt-2 text-xs text-amber-400 space-y-0.5">
                                                {#each inst.errors as e (e)}<li class="break-words">{e}</li>{/each}
                                            </ul>
                                        {/if}
                                    {:else}
                                        <p class="text-xs text-slate-400">No report yet. Run an instrument check while the RTS is idle (tracking jobs report automatically when they start).</p>
                                    {/if}
                                </div>
                                <div class="bg-slate-900/50 rounded-lg p-3">
                                    {@render section(tq ? "Live tracking" : "Jobs")}
                                    {#if tq}
                                        {@render kv([
                                            ["Data rate", tq.rate_hz != null ? `${tq.rate_hz.toFixed(2)} Hz` : null],
                                            ["Last measurement", tq.last_measurement_age != null ? `${fmtDuration(tq.last_measurement_age)} ago` : null],
                                            ["Without distance", tq.no_distance_ratio != null ? `${(tq.no_distance_ratio * 100).toFixed(0)} %` : null],
                                            ["Return code ≠ 0", tq.error_ratio != null ? `${(tq.error_ratio * 100).toFixed(0)} %` : null],
                                            ["Timestamp jitter", tq.timing_residual_std != null ? `${fmtTime(tq.timing_residual_std)} (max ${fmtTime(tq.timing_residual_max)})` : null],
                                            ["Instrument clock drift", tq.clock_drift_ppm != null ? `${tq.clock_drift_ppm.toFixed(2)} ppm` : null],
                                            ["Analysed", `${tq.samples} measurements`],
                                            ["Job running", r.running_job ? fmtDuration(board.server_time - r.running_job.created_at) : null],
                                        ])}
                                    {:else}
                                        {@render kv([
                                            ["Running", r.running_job ? `${JOB_TYPE_NAMES[r.running_job.job_type] ?? r.running_job.job_type} (${fmtDuration(board.server_time - r.running_job.created_at)})` : "–"],
                                            ["Pending", r.pending_jobs],
                                            ["Last job", r.last_job ? `${JOB_TYPE_NAMES[r.last_job.job_type] ?? r.last_job.job_type} – ${r.last_job.job_status}, ${fmtDuration(board.server_time - r.last_job.created_at)} ago` : "–"],
                                        ])}
                                    {/if}
                                </div>
                            </div>
                        </div>
                    {/each}
                </div>
            {/if}
        </div>

        <!-- Devices -->
        <div>
            <h3 class="font-semibold mb-3">Devices &amp; workers</h3>
            {#if sessionDevices.length === 0 && otherDevices.length === 0}
                <div class="bg-slate-800 rounded-xl border border-slate-700 p-6 text-center text-slate-400">
                    No devices assigned or online.
                </div>
            {/if}
            <div class="space-y-3 sm:space-y-4">
                {#each sessionDevices as d (d.device_id)}
                    {@render deviceCard(d)}
                {/each}
                {#each otherDevices as d (d.device_id)}
                    {@render deviceCard(d)}
                {/each}
            </div>
        </div>

        <!-- External sensors -->
        {#if board.external_sensors.length}
            <div>
                <h3 class="font-semibold mb-3">External sensors</h3>
                <div class="grid gap-3 sm:gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {#each board.external_sensors as s (s.id)}
                        {@const id = `sensor-${s.id}`}
                        <div
                            {id}
                            class="bg-slate-800 rounded-xl border p-4 scroll-mt-4 {s.logging_active ? STATUS_BORDER[s.status] : 'border-slate-700'} {selected === id ? 'ring-2 ring-blue-500/60' : ''}"
                        >
                            <div class="flex items-center justify-between gap-2 mb-2">
                                <div class="min-w-0">
                                    <div class="font-semibold text-white">📍 {s.name}</div>
                                    <div class="text-xs text-slate-400 font-mono">{s.ip}</div>
                                </div>
                                {@render pill(s.logging_active ? s.status : "info", s.logging_active ? undefined : "Not logging")}
                            </div>
                            <CheckList checks={s.checks} />
                        </div>
                    {/each}
                </div>
            </div>
        {/if}

        <p class="text-xs text-slate-500">
            <span class={STATUS_TEXT.unknown}>Unverified</span> checks count as not ok: the board only shows
            "All checks passed" if every device, worker, instrument and clock of this session has been verified.
        </p>
    {/if}
</div>
