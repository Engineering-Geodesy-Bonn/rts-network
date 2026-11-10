<!--
    Plan view (easting/northing, equal scale) of the tracked prisms and the stations.
    Pan with drag, zoom with wheel or pinch; "fit" re-centers on all data.
-->
<script lang="ts" module>
    export interface PlanTrack {
        label: string;
        color: string;
        x: number[];
        y: number[];
        station: { x: number; y: number } | null;
        /** Highlight the last point (live) */
        current: boolean;
        stale: boolean;
    }
</script>

<script lang="ts">
    import { onMount } from 'svelte';
    import { cssVar, theme } from '../../theme.svelte';
    import Icon from '../ui/Icon.svelte';

    let { tracks, version = 0, height = 360, follow = true }: { tracks: PlanTrack[]; version?: number; height?: number; follow?: boolean } = $props();

    let canvas: HTMLCanvasElement;
    let wrapper: HTMLDivElement;
    let width = $state(600);
    // view: center and scale (px per m); null = auto fit
    let view = $state<{ cx: number; cy: number; scale: number } | null>(null);
    let frame = 0;

    function bounds(): [number, number, number, number] | null {
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        for (const t of tracks) {
            for (let i = 0; i < t.x.length; i++) {
                const x = t.x[i], y = t.y[i];
                if (x == null || y == null) continue;
                if (x < minX) minX = x;
                if (x > maxX) maxX = x;
                if (y < minY) minY = y;
                if (y > maxY) maxY = y;
            }
            if (t.station) {
                minX = Math.min(minX, t.station.x);
                maxX = Math.max(maxX, t.station.x);
                minY = Math.min(minY, t.station.y);
                maxY = Math.max(maxY, t.station.y);
            }
        }
        return isFinite(minX) ? [minX, minY, maxX, maxY] : null;
    }

    function fitView(): { cx: number; cy: number; scale: number } {
        const b = bounds();
        if (!b) return { cx: 0, cy: 0, scale: 10 };
        const [minX, minY, maxX, maxY] = b;
        const spanX = Math.max(maxX - minX, 1);
        const spanY = Math.max(maxY - minY, 1);
        const scale = Math.min((width - 60) / spanX, (height - 60) / spanY);
        return { cx: (minX + maxX) / 2, cy: (minY + maxY) / 2, scale };
    }

    function niceStep(raw: number): number {
        const p = 10 ** Math.floor(Math.log10(raw));
        const f = raw / p;
        return (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * p;
    }

    function draw(): void {
        frame = 0;
        if (!canvas) return;
        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.round(width * dpr);
        canvas.height = Math.round(height * dpr);
        const ctx = canvas.getContext('2d')!;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, width, height);
        const v = view ?? fitView();
        const sx = (x: number) => width / 2 + (x - v.cx) * v.scale;
        const sy = (y: number) => height / 2 - (y - v.cy) * v.scale;

        // grid with coordinates relative to a rounded origin (UTM numbers are too long for labels)
        const grid = cssVar('--plot-grid');
        const axis = cssVar('--plot-axis');
        const step = niceStep(80 / v.scale);
        const x0 = v.cx - width / 2 / v.scale, x1 = v.cx + width / 2 / v.scale;
        const y0 = v.cy - height / 2 / v.scale, y1 = v.cy + height / 2 / v.scale;
        const originStep = step * 10;
        const ox = Math.floor(v.cx / originStep) * originStep;
        const oy = Math.floor(v.cy / originStep) * originStep;
        ctx.strokeStyle = grid;
        ctx.fillStyle = axis;
        ctx.lineWidth = 1;
        ctx.font = '11px system-ui, sans-serif';
        const decimals = Math.max(0, -Math.floor(Math.log10(step)));
        for (let gx = Math.ceil(x0 / step) * step; gx <= x1; gx += step) {
            const px = Math.round(sx(gx)) + 0.5;
            ctx.beginPath();
            ctx.moveTo(px, 0);
            ctx.lineTo(px, height);
            ctx.stroke();
            ctx.fillText((gx - ox).toFixed(decimals), px + 3, height - 4);
        }
        for (let gy = Math.ceil(y0 / step) * step; gy <= y1; gy += step) {
            const py = Math.round(sy(gy)) + 0.5;
            ctx.beginPath();
            ctx.moveTo(0, py);
            ctx.lineTo(width, py);
            ctx.stroke();
            ctx.fillText((gy - oy).toFixed(decimals), 3, py - 3);
        }
        ctx.fillText(`E ${ox.toFixed(0)} / N ${oy.toFixed(0)} + grid ${step} m`, 6, 14);

        // stations
        for (const t of tracks) {
            if (!t.station) continue;
            const px = sx(t.station.x), py = sy(t.station.y);
            ctx.fillStyle = t.color;
            ctx.beginPath();
            ctx.moveTo(px, py - 8);
            ctx.lineTo(px + 7, py + 5);
            ctx.lineTo(px - 7, py + 5);
            ctx.closePath();
            ctx.fill();
            ctx.fillStyle = axis;
            ctx.fillText(t.label, px + 9, py + 4);
        }

        // tracks
        for (const t of tracks) {
            const n = t.x.length;
            if (!n) continue;
            ctx.strokeStyle = t.color;
            ctx.globalAlpha = t.stale ? 0.45 : 0.9;
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            let started = false;
            for (let i = 0; i < n; i++) {
                const x = t.x[i], y = t.y[i];
                if (x == null || y == null) {
                    started = false;
                    continue;
                }
                if (!started) ctx.moveTo(sx(x), sy(y));
                else ctx.lineTo(sx(x), sy(y));
                started = true;
            }
            ctx.stroke();
            ctx.globalAlpha = 1;
            if (t.current) {
                const px = sx(t.x[n - 1]), py = sy(t.y[n - 1]);
                ctx.fillStyle = t.color;
                ctx.beginPath();
                ctx.arc(px, py, 6, 0, Math.PI * 2);
                ctx.fill();
                ctx.strokeStyle = cssVar('--surface');
                ctx.lineWidth = 2;
                ctx.stroke();
            }
        }

        // scale bar
        const barM = niceStep(100 / v.scale);
        const barPx = barM * v.scale;
        ctx.strokeStyle = axis;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(width - 12 - barPx, height - 26);
        ctx.lineTo(width - 12, height - 26);
        ctx.stroke();
        ctx.fillStyle = axis;
        ctx.fillText(`${barM} m`, width - 12 - barPx, height - 31);
    }

    function schedule(): void {
        if (!frame) frame = requestAnimationFrame(draw);
    }

    // ── interaction ────────────────────────────────────────────────────
    let pointers = new Map<number, { x: number; y: number }>();
    let pinchDistance = 0;

    function current(): { cx: number; cy: number; scale: number } {
        return view ?? fitView();
    }

    function onwheel(e: WheelEvent): void {
        e.preventDefault();
        const v = current();
        const rect = canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left, my = e.clientY - rect.top;
        const factor = Math.exp(-e.deltaY * 0.0015);
        const wx = v.cx + (mx - width / 2) / v.scale;
        const wy = v.cy - (my - height / 2) / v.scale;
        const scale = v.scale * factor;
        view = { scale, cx: wx - (mx - width / 2) / scale, cy: wy + (my - height / 2) / scale };
    }

    function onpointerdown(e: PointerEvent): void {
        canvas.setPointerCapture(e.pointerId);
        pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
        if (pointers.size === 2) {
            const [a, b] = [...pointers.values()];
            pinchDistance = Math.hypot(a.x - b.x, a.y - b.y);
        }
    }

    function onpointermove(e: PointerEvent): void {
        const previous = pointers.get(e.pointerId);
        if (!previous) return;
        pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
        const v = current();
        if (pointers.size === 1) {
            view = { ...v, cx: v.cx - (e.clientX - previous.x) / v.scale, cy: v.cy + (e.clientY - previous.y) / v.scale };
        } else if (pointers.size === 2) {
            const [a, b] = [...pointers.values()];
            const distance = Math.hypot(a.x - b.x, a.y - b.y);
            if (pinchDistance > 0) view = { ...v, scale: v.scale * (distance / pinchDistance) };
            pinchDistance = distance;
        }
    }

    function onpointerup(e: PointerEvent): void {
        pointers.delete(e.pointerId);
        pinchDistance = 0;
    }

    onMount(() => {
        width = wrapper.clientWidth || 300;
        const observer = new ResizeObserver(() => {
            width = wrapper.clientWidth || width;
            schedule();
        });
        observer.observe(wrapper);
        canvas.addEventListener('wheel', onwheel, { passive: false });
        return () => {
            observer.disconnect();
            canvas.removeEventListener('wheel', onwheel);
            cancelAnimationFrame(frame);
        };
    });

    $effect(() => {
        void version;
        void tracks;
        void view;
        void height;
        void width;
        void theme.version;
        schedule();
    });
</script>

<div bind:this={wrapper} class="relative w-full select-none overflow-hidden" style="height: {height}px">
    <canvas
        bind:this={canvas}
        style="width: {width}px; height: {height}px; touch-action: none"
        class="cursor-grab active:cursor-grabbing"
        ondblclick={() => (view = null)}
        {onpointerdown}
        {onpointermove}
        {onpointerup}
        onpointercancel={onpointerup}
    ></canvas>
    {#if view}
        <button
            class="absolute right-2 top-2 inline-flex items-center gap-1 rounded-md border border-line bg-surface px-2 py-1 text-xs text-muted shadow-sm hover:text-fg"
            onclick={() => (view = null)}
        >
            <Icon name="zoomReset" size={14} /> Fit
        </button>
    {/if}
</div>
