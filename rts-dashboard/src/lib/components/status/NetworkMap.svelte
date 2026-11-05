<script lang="ts">
    import type {
        CheckStatus,
        DeviceBoardEntry,
        ExternalSensorBoardEntry,
        RTSBoardEntry,
        StatusBoardResponse,
    } from "../../api/types";
    import { STATUS_HEX, fmtSignedTime, fmtTime } from "../../status";

    let {
        board,
        apiStatus,
        dashboardRtt,
        selected,
        onselect,
    }: {
        board: StatusBoardResponse;
        apiStatus: CheckStatus;
        dashboardRtt: number | null;
        selected: string | null;
        onselect: (id: string) => void;
    } = $props();

    const COL = 184;
    const NODE_W = 166;
    const NODE_H = 70;
    const ROW_API = 16;
    const ROW_DEVICE = 176;
    const ROW_RTS = 336;
    const MARGIN = 16;

    interface MapNode {
        id: string;
        x: number;
        y: number;
        status: CheckStatus;
        icon: string;
        lines: string[];
        dimmed?: boolean;
    }
    interface MapEdge {
        from: MapNode;
        to: MapNode;
        status: CheckStatus;
        label?: string;
        dashed?: boolean;
    }

    function clip(text: string, max = 24): string {
        return text.length > max ? text.slice(0, max - 1) + "…" : text;
    }

    function deviceLines(d: DeviceBoardEntry): string[] {
        const name = d.hostname ? `${d.hostname}` : d.ip;
        const workers = d.workers.filter((w) => w.online).length;
        const second = d.hostname
            ? `${d.ip} · ${workers} worker${workers !== 1 ? "s" : ""}`
            : `${workers} worker${workers !== 1 ? "s" : ""}`;
        if (!d.online) return [name, second, "offline"];
        if (!d.reports_health) return [name, second, "no health reports"];
        const gps = d.gps;
        const fix =
            gps && gps.available
                ? `${gps.mode === 3 ? "3D" : gps.mode === 2 ? "2D" : "no fix"} ${gps.satellites_used ?? "?"}/${gps.satellites_visible ?? "?"}`
                : "GNSS ?";
        const pps = d.checks.find((c) => c.key === "pps");
        const ppsText = pps ? `PPS ${pps.status === "ok" ? "✓" : "✕"}` : "";
        const t = d.chrony?.tracking;
        const err = t
            ? `±${fmtTime(Math.abs(t.system_time_offset) + t.root_dispersion + t.root_delay / 2)}`
            : "";
        return [name, second, `🛰 ${fix} · ${ppsText} · ${err}`];
    }

    function rtsLines(r: RTSBoardEntry): string[] {
        let state = "Idle";
        if (r.state === "running" && r.running_job) {
            const rate = r.tracking?.rate_hz;
            state =
                r.running_job.job_type === "track_prism" ||
                r.running_job.job_type === "dummy_tracking"
                    ? `Tracking ${rate != null ? rate.toFixed(1) + " Hz" : ""}`
                    : r.running_job.job_type.replace(/_/g, " ");
        } else if (r.state === "pending") state = `${r.pending_jobs} job(s) pending`;
        const battery =
            r.instrument?.battery_capacity != null
                ? `🔋 ${r.instrument.battery_capacity} %`
                : "🔋 ?";
        const port = r.port.split("/").pop() ?? r.port;
        return [r.name, state, `${battery} · ${port}`];
    }

    function sensorLines(s: ExternalSensorBoardEntry): string[] {
        return [
            s.name,
            s.ip,
            `${s.online ? "online" : "offline"} · ${s.logging_active ? "logging" : "not logging"}`,
        ];
    }

    let layout = $derived.by(() => {
        const groups: {
            device: DeviceBoardEntry | null;
            deviceId: string;
            rts: RTSBoardEntry[];
        }[] = board.devices.map((d) => ({
            device: d,
            deviceId: d.device_id,
            rts: board.rts.filter((r) => r.device_id === d.device_id),
        }));
        // RTS whose device is unknown to the API
        const known = new Set(board.devices.map((d) => d.device_id));
        const orphans = board.rts.filter((r) => !known.has(r.device_id));
        for (const id of new Set(orphans.map((r) => r.device_id))) {
            groups.push({
                device: null,
                deviceId: id,
                rts: orphans.filter((r) => r.device_id === id),
            });
        }

        const totalCols =
            groups.reduce((n, g) => n + Math.max(1, g.rts.length), 0) +
            board.external_sensors.length;
        const width = Math.max(totalCols * COL + 2 * MARGIN, 2 * COL + 2 * MARGIN + 40);
        const hasRts = board.rts.length > 0;
        const height = (hasRts ? ROW_RTS : ROW_DEVICE) + NODE_H + MARGIN;

        const nodes: MapNode[] = [];
        const edges: MapEdge[] = [];

        const api: MapNode = {
            id: "api",
            x: width / 2 - NODE_W / 2,
            y: ROW_API,
            status: apiStatus,
            icon: "🗄",
            lines: [
                "RTS API",
                apiStatus === "fail" ? "not reachable" : "online",
                `server time ${new Date(board.server_time * 1000).toLocaleTimeString()}`,
            ],
        };
        const dashboard: MapNode = {
            id: "dashboard",
            x: MARGIN,
            y: ROW_API,
            status: apiStatus,
            icon: "💻",
            lines: ["This dashboard", "browser", `RTT ${fmtTime(dashboardRtt)}`],
        };
        nodes.push(api);
        if (api.x - dashboard.x > NODE_W + 20) {
            nodes.push(dashboard);
            edges.push({ from: dashboard, to: api, status: apiStatus });
        }

        let col = 0;
        const usedWidth = totalCols * COL;
        const offsetX = (width - usedWidth) / 2;
        for (const g of groups) {
            const cols = Math.max(1, g.rts.length);
            const centerX = offsetX + (col + cols / 2) * COL;
            const d = g.device;
            const deviceNode: MapNode = d
                ? {
                      id: `device-${d.device_id}`,
                      x: centerX - NODE_W / 2,
                      y: ROW_DEVICE,
                      status: d.in_session ? d.status : "info",
                      icon: "🖥",
                      lines: deviceLines(d),
                      dimmed: !d.in_session,
                  }
                : {
                      id: `device-${g.deviceId}`,
                      x: centerX - NODE_W / 2,
                      y: ROW_DEVICE,
                      status: "fail",
                      icon: "🖥",
                      lines: ["Unknown device", g.deviceId.slice(0, 8), "not registered"],
                  };
            nodes.push(deviceNode);
            let label: string | undefined;
            if (d?.clock) {
                // device clock relative to the API server clock
                label = `Δ ${fmtSignedTime(-d.clock.offset)} · RTT ${fmtTime(d.clock.delay)}`;
            }
            edges.push({
                from: api,
                to: deviceNode,
                status: d
                    ? d.online
                        ? d.reports_health
                            ? "ok"
                            : "warn"
                        : "fail"
                    : "fail",
                label,
                dashed: !d?.online,
            });

            g.rts.forEach((r, i) => {
                const rtsNode: MapNode = {
                    id: `rts-${r.rts_id}`,
                    x: offsetX + (col + i + 0.5) * COL - NODE_W / 2,
                    y: ROW_RTS,
                    status: r.status,
                    icon: "📡",
                    lines: rtsLines(r),
                };
                nodes.push(rtsNode);
                const serial = r.checks.find((c) => c.key === "serial_port");
                edges.push({
                    from: deviceNode,
                    to: rtsNode,
                    status: serial?.status === "ok" ? r.status : (serial?.status ?? "unknown"),
                    dashed: r.state !== "running",
                });
            });
            col += cols;
        }

        for (const s of board.external_sensors) {
            const node: MapNode = {
                id: `sensor-${s.id}`,
                x: offsetX + (col + 0.5) * COL - NODE_W / 2,
                y: ROW_DEVICE,
                status: s.logging_active ? s.status : "info",
                icon: "📍",
                lines: sensorLines(s),
                dimmed: !s.logging_active,
            };
            nodes.push(node);
            edges.push({
                from: api,
                to: node,
                status: s.online ? "ok" : s.logging_active ? "fail" : "unknown",
                dashed: !s.online,
            });
            col += 1;
        }

        return { width, height, nodes, edges };
    });

    function edgePath(e: MapEdge): string {
        const sameRow = Math.abs(e.from.y - e.to.y) < 1;
        if (sameRow) {
            const y = e.from.y + NODE_H / 2;
            return `M ${e.from.x + NODE_W} ${y} L ${e.to.x} ${y}`;
        }
        const x1 = e.from.x + NODE_W / 2;
        const y1 = e.from.y + NODE_H;
        const x2 = e.to.x + NODE_W / 2;
        const y2 = e.to.y;
        const my = (y1 + y2) / 2;
        return `M ${x1} ${y1} C ${x1} ${my}, ${x2} ${my}, ${x2} ${y2}`;
    }

    function labelPos(e: MapEdge): { x: number; y: number } {
        const x1 = e.from.x + NODE_W / 2;
        const x2 = e.to.x + NODE_W / 2;
        const y1 = e.from.y + NODE_H;
        const y2 = e.to.y;
        return { x: (x1 + x2) / 2 + (x2 - x1) * 0.18, y: y1 + (y2 - y1) * 0.62 };
    }

    function activate(id: string) {
        if (id !== "api" && id !== "dashboard") onselect(id);
    }
</script>

<div class="overflow-x-auto -mx-1 px-1">
    <svg
        viewBox="0 0 {layout.width} {layout.height}"
        style="min-width: {Math.min(layout.width, Math.max(560, layout.width * 0.7))}px; max-width: {layout.width * 1.15}px"
        class="w-full h-auto select-none mx-auto block"
        role="img"
        aria-label="Network map"
    >
        <!-- edges -->
        {#each layout.edges as e, i (i)}
            <path
                d={edgePath(e)}
                fill="none"
                stroke={STATUS_HEX[e.status]}
                stroke-opacity="0.75"
                stroke-width="2"
                stroke-dasharray={e.dashed ? "5 5" : undefined}
            />
            {#if e.label}
                {@const p = labelPos(e)}
                <g transform="translate({p.x}, {p.y})">
                    <rect
                        x={-e.label.length * 3.1 - 6}
                        y="-10"
                        width={e.label.length * 6.2 + 12}
                        height="18"
                        rx="9"
                        fill="#0f172a"
                        stroke="#334155"
                    />
                    <text
                        text-anchor="middle"
                        y="3"
                        font-size="10.5"
                        fill="#cbd5e1"
                        font-family="ui-monospace, monospace">{e.label}</text
                    >
                </g>
            {/if}
        {/each}

        <!-- nodes -->
        {#each layout.nodes as n (n.id)}
            <!-- svelte-ignore a11y_no_static_element_interactions, a11y_no_noninteractive_tabindex -->
            <g
                transform="translate({n.x}, {n.y})"
                class={n.id === "api" || n.id === "dashboard" ? "" : "cursor-pointer"}
                opacity={n.dimmed ? 0.55 : 1}
                onclick={() => activate(n.id)}
                onkeydown={(ev) => ev.key === "Enter" && activate(n.id)}
                tabindex={n.id === "api" || n.id === "dashboard" ? undefined : 0}
                role={n.id === "api" || n.id === "dashboard" ? undefined : "button"}
            >
                <title>{n.lines.join("\n")}</title>
                <rect
                    width={NODE_W}
                    height={NODE_H}
                    rx="10"
                    fill={selected === n.id ? "#334155" : "#1e293b"}
                    stroke={STATUS_HEX[n.status]}
                    stroke-width={selected === n.id ? 3 : 1.75}
                />
                <circle cx={NODE_W - 13} cy="13" r="5" fill={STATUS_HEX[n.status]} />
                <text x="10" y="21" font-size="13" font-weight="600" fill="#f1f5f9"
                    >{n.icon} {clip(n.lines[0], 18)}</text
                >
                <text x="10" y="40" font-size="10.5" fill="#94a3b8">{clip(n.lines[1], 27)}</text>
                <text x="10" y="58" font-size="10.5" fill="#cbd5e1">{clip(n.lines[2], 30)}</text>
            </g>
        {/each}
    </svg>
</div>
