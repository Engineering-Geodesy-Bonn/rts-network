<script lang="ts" module>
    // 24×24 stroke icons (Lucide style)
    const PATHS: Record<string, string> = {
        activity: 'M22 12h-4l-3 9L9 3l-3 9H2',
        play: 'M6 4l14 8-14 8z',
        stop: 'M6 6h12v12H6z',
        target: 'M12 2a10 10 0 1 0 0 20 10 10 0 1 0 0-20M12 6a6 6 0 1 0 0 12 6 6 0 1 0 0-12M12 10a2 2 0 1 0 0 4 2 2 0 1 0 0-4',
        crosshair: 'M12 2v4M12 18v4M2 12h4M18 12h4M12 7a5 5 0 1 0 0 10 5 5 0 1 0 0-10',
        list: 'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01',
        heart: 'M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8z',
        settings: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
        sliders: 'M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6',
        plus: 'M12 5v14M5 12h14',
        x: 'M18 6L6 18M6 6l12 12',
        check: 'M20 6L9 17l-5-5',
        alert: 'M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01',
        info: 'M12 2a10 10 0 1 0 0 20 10 10 0 1 0 0-20M12 16v-4M12 8h.01',
        download: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3',
        trash: 'M3 6h18M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2',
        edit: 'M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z',
        chevronLeft: 'M15 18l-6-6 6-6',
        chevronRight: 'M9 18l6-6-6-6',
        chevronDown: 'M6 9l6 6 6-6',
        more: 'M12 12h.01M19 12h.01M5 12h.01',
        wifi: 'M5 12.6a10 10 0 0 1 14 0M8.5 16.1a5 5 0 0 1 7 0M12 20h.01M2 8.8a15 15 0 0 1 20 0',
        wifiOff: 'M2 2l20 20M8.5 16.1a5 5 0 0 1 7 0M12 20h.01M16.7 11.1A10 10 0 0 1 19 12.6M5 12.6a10 10 0 0 1 5.2-2.7M10.7 5.1A15 15 0 0 1 22 8.8M2 8.8a15 15 0 0 1 4.2-2.6',
        cpu: 'M9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2M6 4h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM9 9h6v6H9z',
        satellite: 'M13 7L9 3 5 7l4 4M17 11l4 4-4 4-4-4M8 12l4 4M16 8l-4 4M3 21c2-2 4-3 6-3',
        refresh: 'M21 12a9 9 0 0 1-15.5 6.2L3 16M3 21v-5h5M3 12a9 9 0 0 1 15.5-6.2L21 8M21 3v5h-5',
        flip: 'M17 1l4 4-4 4M3 11V9a4 4 0 0 1 4-4h14M7 23l-4-4 4-4M21 13v2a4 4 0 0 1-4 4H3',
        bell: 'M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0',
        pin: 'M12 22s7-5.5 7-12a7 7 0 1 0-14 0c0 6.5 7 12 7 12zM12 7a3 3 0 1 0 0 6 3 3 0 1 0 0-6',
        layers: 'M12 2l10 5-10 5L2 7zM2 17l10 5 10-5M2 12l10 5 10-5',
        clock: 'M12 2a10 10 0 1 0 0 20 10 10 0 1 0 0-20M12 6v6l4 2',
        sun: 'M12 7a5 5 0 1 0 0 10 5 5 0 1 0 0-10M12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4',
        moon: 'M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z',
        folder: 'M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z',
        link: 'M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7',
        battery: 'M2 7h16a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H2zM22 11v2',
        zoomReset: 'M3 3h6M3 3v6M21 3h-6M21 3v6M3 21h6M3 21v-6M21 21h-6M21 21v-6',
    };
</script>

<script lang="ts">
    let { name, size = 18, class: className = '' }: { name: keyof typeof PATHS | string; size?: number; class?: string } = $props();
</script>

<svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="shrink-0 {className}"
    aria-hidden="true"
>
    <path d={PATHS[name] ?? PATHS.info} />
</svg>
