<script lang="ts">
    import { api } from '../api';
    import { EDM_MEASUREMENT_MODES, FINE_ADJUST_POSITION_MODES, PRISM_TYPES, TMC_INCLINATION_MODES, TMC_MEASUREMENT_MODES, units } from '../format';
    import { store } from '../store.svelte';
    import { toast } from '../toast.svelte';
    import type { RTS, TrackingSettings } from '../types';
    import Button from './ui/Button.svelte';
    import Field from './ui/Field.svelte';
    import Modal from './ui/Modal.svelte';

    let { open = $bindable(false), rts }: { open?: boolean; rts: RTS | null } = $props();

    const DEFAULTS: TrackingSettings = {
        tmc_measurement_mode: 1,
        tmc_inclination_mode: 1,
        edm_measurement_mode: 9,
        prism_type: 3,
        fine_adjust_position_mode: 1,
        fine_adjust_horizontal_search_range: 0.0872,
        fine_adjust_vertical_search_range: 0.0872,
        power_search_area_dcenterhz: 0,
        power_search_area_dcenterv: 1.5708,
        power_search_area_drangehz: 6.283,
        power_search_area_drangev: 0.6,
        power_search_area_enabled: 1,
        power_search_min_range: 1,
        power_search_max_range: 50,
        power_search: true,
    };

    // angles shown in gon
    const ANGLE_KEYS = [
        'fine_adjust_horizontal_search_range',
        'fine_adjust_vertical_search_range',
        'power_search_area_dcenterhz',
        'power_search_area_dcenterv',
        'power_search_area_drangehz',
        'power_search_area_drangev',
    ] as const;

    let form = $state<Record<string, number | boolean>>({});
    let busy = $state(false);

    function load(settings: TrackingSettings) {
        const f: Record<string, number | boolean> = { ...settings };
        for (const key of ANGLE_KEYS) f[key] = Number(units.radToGon(settings[key]).toFixed(4));
        form = f;
    }

    $effect(() => {
        if (open && rts) load(rts.tracking);
    });

    async function save() {
        if (!rts) return;
        busy = true;
        const settings = { ...form } as unknown as TrackingSettings;
        for (const key of ANGLE_KEYS) (settings as unknown as Record<string, number>)[key] = units.gonToRad(Number(form[key]));
        for (const key of Object.keys(DEFAULTS) as (keyof TrackingSettings)[]) {
            if (typeof DEFAULTS[key] === 'number') (settings as unknown as Record<string, number>)[key] = Number(settings[key]);
        }
        try {
            await api.updateRts(rts.id, { tracking: settings });
            store.rts = await api.rtsList(store.session!.id);
            toast.ok('Tracking settings saved. They apply to the next tracking job.');
            open = false;
        } catch (e) {
            toast.error((e as Error).message);
        } finally {
            busy = false;
        }
    }
</script>

<Modal bind:open title="Tracking settings · {rts?.name ?? ''}" wide>
    <div class="space-y-6">
        <section class="grid gap-3 sm:grid-cols-2">
            <Field label="Prism">
                <select bind:value={form.prism_type}>{#each Object.entries(PRISM_TYPES) as [v, l] (v)}<option value={Number(v)}>{l}</option>{/each}</select>
            </Field>
            <Field label="EDM mode">
                <select bind:value={form.edm_measurement_mode}>{#each Object.entries(EDM_MEASUREMENT_MODES) as [v, l] (v)}<option value={Number(v)}>{l}</option>{/each}</select>
            </Field>
            <Field label="TMC measurement">
                <select bind:value={form.tmc_measurement_mode}>{#each Object.entries(TMC_MEASUREMENT_MODES) as [v, l] (v)}<option value={Number(v)}>{l}</option>{/each}</select>
            </Field>
            <Field label="Inclination">
                <select bind:value={form.tmc_inclination_mode}>{#each Object.entries(TMC_INCLINATION_MODES) as [v, l] (v)}<option value={Number(v)}>{l}</option>{/each}</select>
            </Field>
        </section>
        <section>
            <h3 class="mb-3 text-sm font-semibold">Fine adjust (ATR)</h3>
            <div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <Field label="Position mode">
                    <select bind:value={form.fine_adjust_position_mode}>{#each Object.entries(FINE_ADJUST_POSITION_MODES) as [v, l] (v)}<option value={Number(v)}>{l}</option>{/each}</select>
                </Field>
                <Field label="Hz search range" unit="gon"><input type="number" step="any" bind:value={form.fine_adjust_horizontal_search_range} /></Field>
                <Field label="V search range" unit="gon"><input type="number" step="any" bind:value={form.fine_adjust_vertical_search_range} /></Field>
            </div>
        </section>
        <section>
            <div class="mb-3 flex items-center justify-between">
                <h3 class="text-sm font-semibold">Power search</h3>
                <label class="flex items-center gap-2 text-sm"><input type="checkbox" bind:checked={form.power_search as boolean} /> Enabled</label>
            </div>
            <div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <Field label="Min range" unit="m"><input type="number" bind:value={form.power_search_min_range} /></Field>
                <Field label="Max range" unit="m"><input type="number" bind:value={form.power_search_max_range} /></Field>
                <Field label="Search area">
                    <select bind:value={form.power_search_area_enabled}><option value={1}>Restricted</option><option value={0}>Full</option></select>
                </Field>
                <Field label="Area center Hz" unit="gon"><input type="number" step="any" bind:value={form.power_search_area_dcenterhz} /></Field>
                <Field label="Area center V" unit="gon"><input type="number" step="any" bind:value={form.power_search_area_dcenterv} /></Field>
                <Field label="Area range Hz" unit="gon"><input type="number" step="any" bind:value={form.power_search_area_drangehz} /></Field>
                <Field label="Area range V" unit="gon"><input type="number" step="any" bind:value={form.power_search_area_drangev} /></Field>
            </div>
        </section>
    </div>
    {#snippet footer()}
        <Button variant="ghost" class="mr-auto" onclick={() => load(DEFAULTS)}>Defaults</Button>
        <Button onclick={() => (open = false)}>Cancel</Button>
        <Button variant="primary" {busy} onclick={save}>Save</Button>
    {/snippet}
</Modal>
