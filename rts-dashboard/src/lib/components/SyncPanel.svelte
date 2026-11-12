<!--
    Time synchronization of two sensors (total stations or external sensors) that follow the
    same moving object: selection, progress of the estimation and the estimated offset.
-->
<script lang="ts">
    import { api } from '../api';
    import { fmtCount, fmtDuration, rtsColor } from '../format';
    import { sensorColor, sensorStore } from '../sensors.svelte';
    import { store } from '../store.svelte';
    import { toast } from '../toast.svelte';
    import TimePlot, { type TimeSeries } from './plots/TimePlot.svelte';
    import Button from './ui/Button.svelte';
    import Field from './ui/Field.svelte';
    import Panel from './ui/Panel.svelte';
    import Tag from './ui/Tag.svelte';

    let sync = $derived(sensorStore.sync);
    let busy = $state(false);

    // the selection follows the server until it is edited here
    let first = $state<string | null>(null);
    let second = $state<string | null>(null);
    let edited = $state(false);
    $effect(() => {
        if (!edited && sync) {
            first = sync.primary_sensor_id;
            second = sync.secondary_sensor_id;
        }
    });

    interface Option {
        id: string;
        label: string;
        color: string;
        kind: 'station' | 'sensor' | 'other';
    }
    let options = $derived.by<Option[]>(() => {
        const list: Option[] = [
            ...store.rts.map((r, i) => ({ id: r.id, label: r.name, color: rtsColor(i), kind: 'station' as const })),
            ...sensorStore.sensors.map((s, i) => ({ id: s.id, label: s.name, color: sensorColor(i), kind: 'sensor' as const })),
        ];
        // a role may point to a station of another session
        for (const id of [sync?.primary_sensor_id, sync?.secondary_sensor_id]) {
            if (id && !list.some((o) => o.id === id)) list.push({ id, label: 'Station of another session', color: '#888', kind: 'other' });
        }
        return list;
    });
    const option = (id: string | null | undefined) => options.find((o) => o.id === id);

    let running = $derived(!!sync && sync.phase !== 'off');
    let changed = $derived(!!sync && (first !== sync.primary_sensor_id || second !== sync.secondary_sensor_id));
    let canStart = $derived(!!first && !!second && first !== second);

    async function apply(primary: string | null, secondary: string | null, message: string) {
        busy = true;
        try {
            await api.setSyncRoles({ primary_sensor_id: primary, secondary_sensor_id: secondary });
            edited = false;
            await sensorStore.refresh(true);
            toast.ok(message);
        } catch (e) {
            toast.error((e as Error).message);
        } finally {
            busy = false;
        }
    }

    async function restart() {
        busy = true;
        try {
            await api.resetSync();
            await sensorStore.refresh(true);
            toast.ok('Estimation restarted');
        } catch (e) {
            toast.error((e as Error).message);
        } finally {
            busy = false;
        }
    }

    const ms = (s: number, digits = 2) => `${s < 0 ? '−' : ''}${Math.abs(s * 1000).toFixed(digits)}`;

    type Step = { title: string; detail: string; state: 'done' | 'active' | 'todo' };
    let steps = $derived.by<Step[]>(() => {
        if (!sync || sync.phase === 'off') return [];
        const order = ['waiting', 'calibrating', 'matching', 'estimating'];
        const at = order.indexOf(sync.phase);
        return [
            {
                title: 'Data from both',
                detail: `${sync.primary_rate_hz.toFixed(1)} Hz · ${sync.secondary_rate_hz.toFixed(1)} Hz`,
                state: sync.primary_rate_hz > 0 && sync.secondary_rate_hz > 0 ? 'done' : 'active',
            },
            {
                title: 'Rough offset',
                detail: `${Math.min(sync.primary_samples, sync.calibration_samples)} / ${Math.min(sync.secondary_samples, sync.calibration_samples)} of ${sync.calibration_samples} positions`,
                state: at >= 2 ? 'done' : at === 1 ? 'active' : 'todo',
            },
            {
                title: 'Fine estimation',
                detail: sync.updates ? `${fmtCount(sync.updates)} updates` : 'needs overlapping motion',
                state: sync.converged ? 'done' : at >= 2 ? 'active' : 'todo',
            },
        ];
    });

    let series = $derived.by<TimeSeries[]>(() => {
        // the first estimates are very uncertain (σ up to 1 s): only show the settled part
        const limit = Math.max(0.05, 10 * (sync?.sigma_delta_t ?? 0));
        const h = (sync?.history ?? []).filter((r) => r[2] <= limit);
        if (h.length === 0) return [];
        const t = h.map((r) => r[0]);
        return [
            { label: 'Δt + σ', color: '#9aa4b2', t, y: h.map((r) => (r[1] + r[2]) * 1000) },
            { label: 'Δt − σ', color: '#9aa4b2', t, y: h.map((r) => (r[1] - r[2]) * 1000) },
            { label: 'Δt', color: '#2f7ef5', t, y: h.map((r) => r[1] * 1000) },
        ];
    });

    let silent = $derived(
        sync
            ? [
                  ...(sync.primary_rate_hz === 0 ? [option(sync.primary_sensor_id)?.label ?? 'The first sensor'] : []),
                  ...(sync.secondary_rate_hz === 0 ? [option(sync.secondary_sensor_id)?.label ?? 'the second sensor'] : []),
              ]
            : [],
    );
    let age = $derived(sync?.started_at ? Date.now() / 1000 - sync.started_at : null);
    // not settling: σ improved by less than 10 % within the last 2 minutes
    let stuck = $derived.by(() => {
        if (!sync || sync.phase !== 'estimating' || sync.converged || (age ?? 0) < 300) return false;
        const now = sync.history.at(-1);
        const before = sync.history.findLast((r) => now && r[0] <= now[0] - 120);
        return !!now && !!before && now[2] > 0.9 * before[2];
    });
</script>

<Panel title="Time synchronization">
    {#snippet actions()}
        {#if sync?.converged}<Tag tone="good" text="Converged" />{:else if running}<Tag tone="accent" text="Running" />{:else}<Tag text="Off" />{/if}
    {/snippet}

    <p class="mb-3 text-[13px] text-muted">
        Estimates the time offset between two sensors that follow the same moving object, e.g. a total station and a GNSS receiver on the same vehicle. It compares the distance both have travelled, so their coordinate
        systems do not matter.
    </p>

    <div class="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <Field label="Reference (first sensor)">
            <select bind:value={first} onchange={() => (edited = true)}>
                <option value={null}>–</option>
                <optgroup label="Total stations">{#each options.filter((o) => o.kind !== 'sensor') as o (o.id)}<option value={o.id}>{o.label}</option>{/each}</optgroup>
                <optgroup label="External sensors">{#each options.filter((o) => o.kind === 'sensor') as o (o.id)}<option value={o.id}>{o.label}</option>{/each}</optgroup>
            </select>
        </Field>
        <Field label="Synchronized (second sensor)">
            <select bind:value={second} onchange={() => (edited = true)}>
                <option value={null}>–</option>
                <optgroup label="Total stations">{#each options.filter((o) => o.kind !== 'sensor') as o (o.id)}<option value={o.id}>{o.label}</option>{/each}</optgroup>
                <optgroup label="External sensors">{#each options.filter((o) => o.kind === 'sensor') as o (o.id)}<option value={o.id}>{o.label}</option>{/each}</optgroup>
            </select>
        </Field>
        <div class="flex gap-2">
            {#if !running || changed}
                <Button variant="primary" icon="play" busy={busy} disabled={!canStart} onclick={() => apply(first, second, 'Synchronization started')}>{running ? 'Switch' : 'Start'}</Button>
            {/if}
            {#if running}
                <Button icon="refresh" disabled={busy} title="Discard the estimate and start again" onclick={restart}>Restart</Button>
                <Button variant="stop" icon="stop" disabled={busy} onclick={() => apply(null, null, 'Synchronization stopped')}>Stop</Button>
            {/if}
        </div>
    </div>
    {#if first && first === second}<p class="mt-2 text-[13px] text-bad">Select two different sensors.</p>{/if}

    {#if sync && running}
        {@const a = option(sync.primary_sensor_id)}
        {@const b = option(sync.secondary_sensor_id)}
        <ol class="mt-4 grid gap-px overflow-hidden rounded-[5px] border border-line bg-line sm:grid-cols-3">
            {#each steps as step, i (step.title)}
                <li class="flex items-start gap-2 bg-surface px-3 py-2">
                    <span
                        class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold {step.state === 'done'
                            ? 'bg-good text-surface'
                            : step.state === 'active'
                              ? 'bg-accent text-accent-fg'
                              : 'bg-surface-2 text-muted'}">{step.state === 'done' ? '✓' : i + 1}</span
                    >
                    <span><span class="block text-[13px] font-semibold">{step.title}</span><span class="num block text-xs text-muted">{step.detail}</span></span>
                </li>
            {/each}
        </ol>

        {#if sync.phase === 'waiting'}
            <p class="mt-3 rounded-[5px] border border-warn/40 bg-warn-soft px-3 py-2 text-[13px] text-warn">
                {silent.join(' and ')} {silent.length > 1 ? 'deliver' : 'delivers'} no positions. A total station must be tracking, an external sensor must stream.
            </p>
        {:else if sync.phase === 'estimating' || sync.phase === 'matching'}
            <div class="mt-4 flex flex-wrap items-end gap-x-8 gap-y-3">
                <div>
                    <div class="label">Δt [ms]</div>
                    <div class="num text-[26px] font-semibold leading-tight">{ms(sync.delta_t)} <span class="text-[15px] font-normal text-muted">± {ms(sync.sigma_delta_t)}</span></div>
                </div>
                <div>
                    <div class="label">Path length bias [m]</div>
                    <div class="num text-[15px]">{sync.bias.toFixed(3)} <span class="text-muted">± {sync.sigma_bias.toFixed(3)}</span></div>
                </div>
                <div>
                    <div class="label">Running for</div>
                    <div class="num text-[15px]">{fmtDuration(age)}</div>
                </div>
            </div>
            <p class="mt-2 text-[13px]">
                Add Δt to the time stamps of
                <span class="inline-flex items-center gap-1 font-semibold"><span class="h-2.5 w-2.5 rounded-full" style="background: {b?.color}"></span>{b?.label}</span>
                to get the time of
                <span class="inline-flex items-center gap-1 font-semibold"><span class="h-2.5 w-2.5 rounded-full" style="background: {a?.color}"></span>{a?.label}</span>.
                {#if !sync.converged}<span class="text-muted">The estimate is still settling.</span>{/if}
            </p>
            {#if stuck}
                <p class="mt-2 rounded-[5px] border border-warn/40 bg-warn-soft px-3 py-2 text-[13px] text-warn">
                    The estimate does not settle. It needs changes in speed: at constant speed a time offset cannot be told apart from a difference in path length.
                </p>
            {/if}
            {#if series.length}
                <div class="mt-3">
                    <div class="label mb-1 flex items-center gap-3">Δt over time <span class="font-normal normal-case tracking-normal text-muted">blue: estimate · grey: ± σ</span></div>
                    <TimePlot {series} yLabel="Δt [ms]" height={170} />
                </div>
            {/if}
        {/if}
    {/if}

    <details class="mt-4 text-[13px] text-muted">
        <summary class="cursor-pointer">How it works</summary>
        <ol class="mt-2 list-decimal space-y-1 pl-5">
            <li>Both sensors must follow the same object, with varying speed (accelerate, brake, curves).</li>
            <li>A rough offset is taken from the receive times of the first {sync?.calibration_samples ?? 20} positions of each sensor.</li>
            <li>A Kalman filter then compares the travelled path lengths at the same time and refines the offset Δt and a path length bias.</li>
            <li>The estimate is kept in memory only. Restart it after changing the setup.</li>
        </ol>
    </details>
</Panel>
