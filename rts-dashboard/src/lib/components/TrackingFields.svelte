<!-- The tracking settings of a station (angles in gon), shared by the station editor and the
     tracking settings dialog of the Measure page. -->
<script lang="ts">
    import { EDM_MEASUREMENT_MODES, FINE_ADJUST_POSITION_MODES, PRISM_TYPES, TMC_INCLINATION_MODES, TMC_MEASUREMENT_MODES } from '../format';
    import type { TrackingForm } from '../tracking';
    import Field from './ui/Field.svelte';

    let { tracking = $bindable() }: { tracking: TrackingForm } = $props();
</script>

<div class="grid gap-3 sm:grid-cols-2">
    <Field label="Prism"><select bind:value={tracking.prism_type}>{#each Object.entries(PRISM_TYPES) as [v, l] (v)}<option value={Number(v)}>{l}</option>{/each}</select></Field>
    <Field label="Distance mode"><select bind:value={tracking.edm_measurement_mode}>{#each Object.entries(EDM_MEASUREMENT_MODES) as [v, l] (v)}<option value={Number(v)}>{l}</option>{/each}</select></Field>
    <Field label="Measurement mode"><select bind:value={tracking.tmc_measurement_mode}>{#each Object.entries(TMC_MEASUREMENT_MODES) as [v, l] (v)}<option value={Number(v)}>{l}</option>{/each}</select></Field>
    <Field label="Inclination"><select bind:value={tracking.tmc_inclination_mode}>{#each Object.entries(TMC_INCLINATION_MODES) as [v, l] (v)}<option value={Number(v)}>{l}</option>{/each}</select></Field>
    <Field label="Fine adjust mode"><select bind:value={tracking.fine_adjust_position_mode}>{#each Object.entries(FINE_ADJUST_POSITION_MODES) as [v, l] (v)}<option value={Number(v)}>{l}</option>{/each}</select></Field>
    <div class="grid grid-cols-2 gap-3">
        <Field label="Search Hz" unit="gon"><input type="number" step="any" bind:value={tracking.fine_adjust_horizontal_search_range} /></Field>
        <Field label="Search V" unit="gon"><input type="number" step="any" bind:value={tracking.fine_adjust_vertical_search_range} /></Field>
    </div>
    <label class="flex items-center gap-2 sm:col-span-2"><input type="checkbox" bind:checked={tracking.power_search as boolean} /> Power search when the prism is lost</label>
    {#if tracking.power_search}
        <div class="grid grid-cols-2 gap-3 sm:col-span-2 sm:grid-cols-4">
            <Field label="Min range" unit="m"><input type="number" bind:value={tracking.power_search_min_range} /></Field>
            <Field label="Max range" unit="m"><input type="number" bind:value={tracking.power_search_max_range} /></Field>
            <Field label="Area center Hz" unit="gon"><input type="number" step="any" bind:value={tracking.power_search_area_dcenterhz} /></Field>
            <Field label="Area center V" unit="gon"><input type="number" step="any" bind:value={tracking.power_search_area_dcenterv} /></Field>
            <Field label="Area width Hz" unit="gon"><input type="number" step="any" bind:value={tracking.power_search_area_drangehz} /></Field>
            <Field label="Area height V" unit="gon"><input type="number" step="any" bind:value={tracking.power_search_area_drangev} /></Field>
            <Field label="Restrict area"><select bind:value={tracking.power_search_area_enabled}><option value={1}>Yes</option><option value={0}>No</option></select></Field>
        </div>
    {/if}
</div>
