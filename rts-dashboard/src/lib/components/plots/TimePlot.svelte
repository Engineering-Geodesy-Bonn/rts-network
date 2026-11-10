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
    import { cssVar, theme } from '../../theme.svelte';

    let {
        series,
        version = 0,
        yLabel = '',
        height = 220,
        follow = 0,
        now = () => Date.now() / 1000,
        digits = 3,
        onzoom,
    }: {
        series: TimeSeries[];
        version?: number;
        yLabel?: string;
        height?: number;
        follow?: number;
        now?: () => number;
        digits?: number;
        onzoom?: (range: [number, number] | null) => void;
    } = $props();

    let container: HTMLDivElement;
    let plot: uPlot | null = null;
    let zoomed = $state(false);
    let width = $state(600);
    let frame = 0;
    let lastDraw = 0;
    let signature = '';

    function build(): void {
        plot?.destroy();
        const axis = cssVar('--plot-axis');
        const grid = cssVar('--plot-grid');
        const axisStyle = {
            stroke: axis,
            grid: { stroke: grid, width: 1 },
            ticks: { stroke: grid, width: 1 },
            font: '11px system-ui, sans-serif',
        };
        const opts: uPlot.Options = {
            width,
            height,
            pxAlign: 0,
            legend: { show: series.length > 1, live: false },
            cursor: { drag: { x: true, y: false, setScale: true }, points: { size: 6 } },
            scales: { x: { time: true }, y: { auto: true } },
            axes: [
                { ...axisStyle, space: 70 },
                {
                    ...axisStyle,
                    label: yLabel,
                    labelFont: '11px system-ui, sans-serif',
                    labelSize: 16,
                    size: (_u: uPlot, values: string[]) => 18 + 7 * Math.max(4, ...(values ?? []).map((v) => v.length)),
                },
            ],
            series: [
                {},
                ...series.map((s) => ({
                    label: s.label,
                    stroke: s.color,
                    width: 1.5,
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
        plot = new uPlot(opts, data(), container);
        signature = series.map((s) => s.label + s.color).join('|');
        apply();
    }

    function data(): uPlot.AlignedData {
        if (series.length === 0) return [[]];
        if (series.length === 1) return [series[0].t, series[0].y] as uPlot.AlignedData;
        return uPlot.join(series.map((s) => [s.t, s.y] as uPlot.AlignedData));
    }

    function apply(): void {
        if (!plot) return;
        plot.setData(data(), !follow || zoomed);
        if (follow > 0 && !zoomed) {
            const t = now();
            plot.setScale('x', { min: t - follow, max: t });
        }
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
        if (plot) build();
    });
</script>

<div class="relative min-w-0 overflow-hidden">
    <div bind:this={container} class="w-full" ondblclick={resetZoom} role="img" aria-label={yLabel}></div>
    {#if zoomed}
        <button
            class="absolute right-2 top-1 rounded-md border border-line bg-surface px-2 py-0.5 text-xs text-muted shadow-sm hover:text-fg"
            onclick={resetZoom}>{follow ? 'Back to live' : 'Reset zoom'}</button
        >
    {/if}
</div>
