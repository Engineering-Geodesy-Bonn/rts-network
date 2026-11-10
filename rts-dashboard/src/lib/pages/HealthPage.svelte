<script lang="ts">
    import CheckList from '../components/CheckList.svelte';
    import Badge from '../components/ui/Badge.svelte';
    import Button from '../components/ui/Button.svelte';
    import Icon from '../components/ui/Icon.svelte';
    import { clock } from '../clock.svelte';
    import { events } from '../events.svelte';
    import { fmtBytes, fmtDuration, fmtTime, rtsColor, STATUS_LABEL } from '../format';
    import { store } from '../store.svelte';
    import type { CheckStatus } from '../types';

    let board = $derived(store.board);
    let age = $derived(store.boardReceivedAt ? clock.now - store.boardReceivedAt / 1000 : null);
    let stale = $derived(age === null || age > 8 || events.state !== 'open');
    let overall = $derived<CheckStatus>(board && !stale ? board.overall : 'unknown');
    let problems = $derived(board ? board.counts.fail + board.counts.warn + board.counts.unknown : 0);
    let expanded = $state<Record<string, boolean>>({});
    let checking = $state(false);

    const HEADLINE: Record<CheckStatus, string> = {
        ok: 'All checks passed',
        info: 'All checks passed',
        unknown: 'Some checks could not be verified',
        warn: 'Attention needed',
        fail: 'Problems detected',
    };
    const BANNER: Record<CheckStatus, string> = {
        ok: 'border-ok/40 bg-ok-bg',
        info: 'border-ok/40 bg-ok-bg',
        unknown: 'border-line bg-surface-2',
        warn: 'border-warn/40 bg-warn-bg',
        fail: 'border-fail/40 bg-fail-bg',
    };

    async function checkInstruments() {
        checking = true;
        for (const rts of store.rts) {
            if (store.activeJobsOf(rts.id).length === 0) await store.startJob(rts.id, 'health_check');
        }
        checking = false;
    }
</script>

<div class="mb-4 flex flex-wrap items-center gap-2">
    <div class="mr-auto">
        <h1 class="text-xl font-bold">Health</h1>
        <p class="text-sm text-muted">Every device, worker, clock and instrument of this session. Checks that cannot be verified count as not OK.</p>
    </div>
    <Button icon="battery" busy={checking} onclick={checkInstruments}>Check all instruments</Button>
</div>

<div class="mb-4 flex flex-wrap items-center gap-3 rounded-xl border p-4 {BANNER[overall]}">
    <Badge tone={overall} pulse={overall === 'fail'}>{STATUS_LABEL[overall]}</Badge>
    <span class="font-semibold">{stale ? 'Status not up to date' : HEADLINE[overall]}</span>
    <span class="text-sm text-muted">
        {#if stale}
            {events.state !== 'open' ? 'No connection to the server' : 'Waiting for the server'}
        {:else if board}
            {problems} of {Object.values(board.counts).reduce((a, b) => a + b, 0)} checks need attention · updated {fmtDuration(age)} ago
        {/if}
    </span>
</div>

{#if board}
    <div class="grid gap-4 xl:grid-cols-2">
        <section class="rounded-xl border border-line bg-surface p-4 shadow-sm">
            <h2 class="mb-2 font-semibold">Network</h2>
            <CheckList checks={board.network_checks} />
        </section>

        <section class="rounded-xl border border-line bg-surface p-4 shadow-sm">
            <h2 class="mb-2 font-semibold">Total stations</h2>
            {#each board.rts as r (r.rts_id)}
                <div class="border-t border-line py-2 first:border-t-0">
                    <button class="flex w-full items-center gap-2.5 text-left" onclick={() => (expanded[r.rts_id] = !expanded[r.rts_id])}>
                        <span class="h-2.5 w-2.5 rounded-full" style="background: {rtsColor(store.rtsIndex(r.rts_id))}"></span>
                        <span class="font-medium">{r.name}</span>
                        <span class="text-xs text-muted">{r.state}</span>
                        {#if r.tracking?.rate_hz}<span class="text-xs text-muted tabular">{r.tracking.rate_hz.toFixed(1)} Hz</span>{/if}
                        <span class="ml-auto"><Badge tone={r.status}>{STATUS_LABEL[r.status]}</Badge></span>
                        <Icon name={expanded[r.rts_id] ? 'chevronDown' : 'chevronRight'} size={16} class="text-muted" />
                    </button>
                    <div class="mt-1 pl-5">
                        <CheckList checks={r.checks} onlyProblems={!expanded[r.rts_id]} />
                    </div>
                </div>
            {:else}
                <p class="text-sm text-muted">No total stations in this session.</p>
            {/each}
        </section>

        {#each board.devices as d (d.device_id)}
            <section class="rounded-xl border border-line bg-surface p-4 shadow-sm">
                <header class="mb-2 flex flex-wrap items-center gap-2">
                    <Icon name="cpu" class="text-muted" />
                    <h2 class="font-semibold">{d.name || d.hostname || d.ip}</h2>
                    <span class="text-xs text-muted">{d.ip}{d.in_session ? '' : ' · not used in this session'}</span>
                    <span class="ml-auto"><Badge tone={d.status}>{d.online ? STATUS_LABEL[d.status] : 'Offline'}</Badge></span>
                </header>
                <CheckList checks={d.checks} />
                {#if d.workers.length}
                    <h3 class="mt-3 mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Workers</h3>
                    {#each d.workers as w (w.worker_id)}
                        <div class="mb-2 rounded-lg bg-surface-2 px-3 py-2">
                            <div class="flex flex-wrap items-center gap-2 text-sm">
                                <span class="font-mono text-xs">{w.worker_id.slice(0, 8)}</span>
                                <span class="text-xs text-muted">v{w.heartbeat.version}</span>
                                {#if w.heartbeat.runtime.job_type}<span class="text-xs">{w.heartbeat.runtime.job_type}</span>{/if}
                                <span class="text-xs text-muted">
                                    unsent {w.heartbeat.runtime.outbox_backlog}
                                    {#if w.heartbeat.system.cpu_temperature != null} · {w.heartbeat.system.cpu_temperature.toFixed(0)} °C{/if}
                                    {#if w.heartbeat.system.disk_free != null} · {fmtBytes(w.heartbeat.system.disk_free)} free{/if}
                                </span>
                                <span class="ml-auto"><Badge tone={w.status}>{w.online ? STATUS_LABEL[w.status] : 'Stopped'}</Badge></span>
                            </div>
                            <CheckList checks={w.checks} onlyProblems />
                        </div>
                    {/each}
                {/if}
                {#if d.clock}
                    <p class="mt-2 text-xs text-muted">Clock vs. server {fmtTime(d.clock.offset)} (± {fmtTime(d.clock.delay / 2)})</p>
                {/if}
            </section>
        {/each}

        {#if board.external_sensors.length}
            <section class="rounded-xl border border-line bg-surface p-4 shadow-sm">
                <h2 class="mb-2 font-semibold">External sensors</h2>
                {#each board.external_sensors as s (s.id)}
                    <div class="border-t border-line py-2 first:border-t-0">
                        <div class="flex items-center gap-2">
                            <span class="font-medium">{s.name}</span>
                            <span class="text-xs text-muted">{s.ip}</span>
                            <span class="ml-auto"><Badge tone={s.status}>{STATUS_LABEL[s.status]}</Badge></span>
                        </div>
                        <CheckList checks={s.checks} />
                    </div>
                {/each}
            </section>
        {/if}
    </div>
{:else}
    <div class="mt-16 flex justify-center"><span class="h-6 w-6 animate-spin rounded-full border-2 border-muted border-t-transparent"></span></div>
{/if}
