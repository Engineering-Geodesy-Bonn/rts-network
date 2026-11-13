<!--
    Time series of one quantity for several RTS (uPlot).
    follow > 0: the x axis shows the last `follow` seconds up to "now" (live view).
    Dragging selects a zoom range; double click or "reset" returns to following.
-->
<script lang="ts" module>
    export interface TimeSeries {
        label: string;
        color: string;
        t: number[];
        y: number[];
    }
</script>

<script lang="ts">
    import uPlot from 'uplot';
    import 'uplot/dist/uPlot.min.css';
    import { onDestroy, onMount } from 'svelte';
    import { media } from '../../media.svelte';
    import { cssVar, theme } from '../../theme.svelte';

    let {
        series,
        version = 0,
        yLabel = '',
        height = 220,
        follow = 0,
        now = () => Date.now() / 1000,
        onzoom,
        syncKey = '',
        showX = true,
        relative = false,
    }: {
        series: TimeSeries[];
        version?: number;
        yLabel?: string;
        height?: number;
        follow?: number;
        now?: () => number;
        onzoom?: (range: [number, number] | null) => void;
        syncKey?: string;
        showX?: boolean;
        /** x values are seconds since a start (elapsed time) instead of Unix time */
        relative?: boolean;
    } = $props();

    let container: HTMLDivElement;
    let plot: uPlot | null = null;
    let zoomed = $state(false);
    let width = $state(600);
    let frame = 0;
    let lastDraw = 0;
    let signature = '';

    /**
     * Tick steps of the time axis [s]. uPlot's own steps jump from 1 to 5 min, which leaves a
     * narrow plot (phones) with a single label for a few minutes of data.
     */
    const TIME_INCRS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 10800, 21600, 43200, 86400, 172800, 604800];

    function build(): void {
        plot?.destroy();
        const axis = cssVar('--plot-axis');
        const grid = cssVar('--plot-grid');
        const axisStyle = {
            stroke: axis,
            grid: { stroke: grid, width: 1 },
            ticks: { stroke: grid, width: 1 },
            font: '11px ui-monospace, Menlo, Consolas, monospace',
        };
        const opts: uPlot.Options = {
            width,
            height,
            pxAlign: 0,
            legend: { show: false },
            cursor: { drag: { x: true, y: false, setScale: true }, points: { size: 5 }, ...(syncKey ? { sync: { key: syncKey } } : {}) },
            scales: { x: { time: !relative }, y: { auto: true } },
            axes: [
                showX ? { ...axisStyle, space: media.phone ? 64 : 80, incrs: TIME_INCRS, values: relative ? elapsedLabels : timeLabels } : { ...axisStyle, size: 4, values: (_u: uPlot, splits: number[]) => splits.map(() => '') },
                {
                    ...axisStyle,
                    label: yLabel,
                    labelFont: '600 10px system-ui, sans-serif',
                    labelSize: 16,
                    size: media.phone ? 66 : 92, // phones: room for the data
                    values: (_u: uPlot, splits: number[], _axis: number, _space: number, increment: number) => {
                        const decimals = Math.max(0, Math.min(6, -Math.floor(Math.log10(increment || 1) + 1e-9)));
                        return splits.map((v) => v.toFixed(decimals));
                    },
                },
            ],
            series: [
                {},
                ...series.map((s) => ({
                    label: s.label,
                    stroke: s.color,
                    width: 1.25,
                    spanGaps: false,
                    points: { show: false },
                })),
            ],
            hooks: {
                setSelect: [
                    (u: uPlot) => {
                        if (u.select.width > 5) {
                            const min = u.posToVal(u.select.left, 'x');
                            const max = u.posToVal(u.select.left + u.select.width, 'x');
                            zoomed = true;
                            onzoom?.([min, max]);
                        }
                    },
                ],
            },
        };
        lastSeries = series;
        lastData = data();
        plot = new uPlot(opts, lastData, container);
        signature = series.map((s) => s.label + s.color).join('|');
        apply();
    }

    /** 24 h clock labels; seconds (and tenths) when zoomed in, date on the first tick */
    function timeLabels(_u: uPlot, splits: number[], _axis: number, _space: number, increment: number): string[] {
        const pad = (v: number) => String(v).padStart(2, '0');
        return splits.map((v, i) => {
            const d = new Date(v * 1000);
            let text = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
            if (increment < 60) text += `:${pad(d.getSeconds())}`;
            if (increment < 1) text += `.${Math.floor(d.getMilliseconds() / 100)}`;
            if (i === 0 && increment >= 3600) text = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${text}`;
            return text;
        });
    }

    /** Elapsed time: 0:45 · 12:30 · 1:02:03, tenths when zoomed in */
    function elapsedLabels(_u: uPlot, splits: number[], _axis: number, _space: number, increment: number): string[] {
        const pad = (v: number) => String(v).padStart(2, '0');
        return splits.map((v) => {
            const sign = v < 0 ? '−' : '';
            const a = Math.abs(v);
            const s = Math.floor(a);
            let text = a >= 3600 ? `${Math.floor(s / 3600)}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}` : `${Math.floor(s / 60)}:${pad(s % 60)}`;
            if (increment < 1) text += `.${Math.floor((a - s) * 10)}`;
            return sign + text;
        });
    }

    function data(): uPlot.AlignedData {
        if (series.length === 0) return [[]];
        if (series.length === 1) return [series[0].t, series[0].y] as uPlot.AlignedData;
        return uPlot.join(series.map((s) => [s.t, s.y] as uPlot.AlignedData));
    }

    let lastData: uPlot.AlignedData | null = null;
    let lastSeries: TimeSeries[] | null = null;

    function apply(): void {
        if (!plot) return;
        const u = plot;
        // one redraw for new data and the moving time axis
        u.batch(() => {
            if (series !== lastSeries || !lastData) {
                lastSeries = series;
                lastData = data();
                u.setData(lastData, !follow || zoomed);
            }
            if (follow > 0 && !zoomed) {
                const t = now();
                u.setScale('x', { min: t - follow, max: t });
            }
        });
    }

    function schedule(): void {
        if (frame) return;
        const wait = Math.max(0, 200 - (performance.now() - lastDraw));
        frame = window.setTimeout(() => {
            frame = 0;
            lastDraw = performance.now();
            if (series.map((s) => s.label + s.color).join('|') !== signature) build();
            else apply();
        }, wait);
    }

    export function resetZoom(): void {
        zoomed = false;
        onzoom?.(null);
        if (plot) {
            plot.setData(data(), true);
            if (follow > 0) apply();
        }
    }

    onMount(() => {
        width = container.clientWidth || 300;
        build();
        const observer = new ResizeObserver(() => {
            const w = container.clientWidth;
            if (w && Math.abs(w - width) > 2) {
                width = w;
                plot?.setSize({ width, height });
            }
        });
        observer.observe(container);
        // follow mode: keep the time axis moving even when no data arrives
        const ticker = setInterval(() => {
            if (follow > 0 && !zoomed) schedule();
        }, 1000);
        return () => {
            observer.disconnect();
            clearInterval(ticker);
        };
    });

    onDestroy(() => {
        clearTimeout(frame);
        plot?.destroy();
    });

    $effect(() => {
        void version;
        void series;
        void follow;
        schedule();
    });

    $effect(() => {
        void theme.version;
        void height;
        void yLabel;
        void relative;
        void media.phone;
        if (plot) build();
    });
</script>

<div class="relative min-w-0 overflow-hidden">
    <div bind:this={container} class="w-full" ondblclick={resetZoom} role="img" aria-label={yLabel}></div>
    {#if zoomed}
        <button
            class="absolute right-2 top-1 rounded-md border border-line bg-surface px-2.5 py-1 text-[13px] text-muted shadow-sm hover:text-fg md:px-2 md:py-0.5 md:text-xs"
            onclick={resetZoom}>{follow ? 'Back to live' : 'Reset zoom'}</button
        >
    {/if}
</div>
