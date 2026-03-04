<script lang="ts">
    import { onMount } from "svelte";
    import { getTrackingSettings, updateTrackingSettings } from "../api/client";
    import {
        PRISM_TYPES,
        TMC_MEASUREMENT_MODES,
        TMC_INCLINATION_MODES,
        EDM_MEASUREMENT_MODES,
        FINE_ADJUST_POSITION_MODES,
    } from "../constants";

    let {
        rtsId,
        onclose,
    }: {
        rtsId: number;
        onclose: () => void;
    } = $props();

    // Form fields
    let tmc_measurement_mode = $state(1);
    let tmc_inclination_mode = $state(1);
    let edm_measurement_mode = $state(9);
    let prism_type = $state(3);
    let fine_adjust_position_mode = $state(1);
    let fine_adjust_horizontal_search_range = $state(0.0872);
    let fine_adjust_vertical_search_range = $state(0.0872);
    let power_search_area_dcenterhz = $state(0.0);
    let power_search_area_dcenterv = $state(1.5708);
    let power_search_area_drangehz = $state(6.283);
    let power_search_area_drangev = $state(0.6);
    let power_search_area_enabled = $state(1);
    let power_search_min_range = $state(1);
    let power_search_max_range = $state(50);
    let power_search = $state(true);

    let loading = $state(true);
    let saving = $state(false);
    let error = $state("");
    let success = $state("");

    async function load() {
        loading = true;
        error = "";
        try {
            const s = await getTrackingSettings(rtsId);
            tmc_measurement_mode = s.tmc_measurement_mode;
            tmc_inclination_mode = s.tmc_inclination_mode;
            edm_measurement_mode = s.edm_measurement_mode;
            prism_type = s.prism_type;
            fine_adjust_position_mode = s.fine_adjust_position_mode;
            fine_adjust_horizontal_search_range =
                s.fine_adjust_horizontal_search_range;
            fine_adjust_vertical_search_range =
                s.fine_adjust_vertical_search_range;
            power_search_area_dcenterhz = s.power_search_area_dcenterhz;
            power_search_area_dcenterv = s.power_search_area_dcenterv;
            power_search_area_drangehz = s.power_search_area_drangehz;
            power_search_area_drangev = s.power_search_area_drangev;
            power_search_area_enabled = s.power_search_area_enabled;
            power_search_min_range = s.power_search_min_range;
            power_search_max_range = s.power_search_max_range;
            power_search = s.power_search;
        } catch (e: any) {
            error = e.message || "Failed to load tracking settings";
        } finally {
            loading = false;
        }
    }

    async function handleSubmit() {
        saving = true;
        error = "";
        success = "";
        try {
            await updateTrackingSettings(rtsId, {
                tmc_measurement_mode,
                tmc_inclination_mode,
                edm_measurement_mode,
                prism_type,
                fine_adjust_position_mode,
                fine_adjust_horizontal_search_range,
                fine_adjust_vertical_search_range,
                power_search_area_dcenterhz,
                power_search_area_dcenterv,
                power_search_area_drangehz,
                power_search_area_drangev,
                power_search_area_enabled,
                power_search_min_range,
                power_search_max_range,
                power_search,
            });
            success = "Settings saved successfully";
        } catch (e: any) {
            error = e.message || "Failed to save settings";
        } finally {
            saving = false;
        }
    }

    onMount(() => {
        load();
    });
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
    class="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
    onclick={onclose}
    onkeydown={(e) => e.key === "Escape" && onclose()}
    role="dialog"
    tabindex="-1"
>
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
        class="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-lg max-h-[90vh] flex flex-col shadow-2xl"
        onclick={(e) => e.stopPropagation()}
        onkeydown={() => {}}
    >
        <div
            class="p-6 border-b border-slate-700 flex items-center justify-between shrink-0"
        >
            <h2 class="text-xl font-semibold">
                Tracking Settings <span class="text-slate-400 text-sm"
                    >(RTS #{rtsId})</span
                >
            </h2>
            <button
                class="text-slate-400 hover:text-white p-1 cursor-pointer"
                onclick={onclose}
                aria-label="Close"
            >
                <svg
                    class="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                >
                    <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M6 18L18 6M6 6l12 12"
                    />
                </svg>
            </button>
        </div>

        {#if loading}
            <div class="p-12 flex items-center justify-center">
                <div
                    class="inline-block w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full animate-spin"
                ></div>
            </div>
        {:else}
            <form
                class="p-6 space-y-3 overflow-y-auto"
                onsubmit={(e) => {
                    e.preventDefault();
                    handleSubmit();
                }}
            >
                {#if error}
                    <div
                        class="bg-red-500/10 border border-red-500/30 text-red-400 px-3 py-2 rounded-lg text-sm"
                    >
                        {error}
                    </div>
                {/if}
                {#if success}
                    <div
                        class="bg-green-500/10 border border-green-500/30 text-green-400 px-3 py-2 rounded-lg text-sm"
                    >
                        {success}
                    </div>
                {/if}

                <!-- TMC/EDM -->
                <h3
                    class="text-xs font-semibold text-slate-500 uppercase tracking-wider"
                >
                    Measurement Modes
                </h3>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label
                            class="block text-xs text-slate-400 mb-1"
                            for="ts-tmc">TMC Measurement</label
                        >
                        <select
                            id="ts-tmc"
                            bind:value={tmc_measurement_mode}
                            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                        >
                            {#each Object.entries(TMC_MEASUREMENT_MODES) as [val, label]}
                                <option value={Number(val)}>{label}</option>
                            {/each}
                        </select>
                    </div>
                    <div>
                        <label
                            class="block text-xs text-slate-400 mb-1"
                            for="ts-incl">TMC Inclination</label
                        >
                        <select
                            id="ts-incl"
                            bind:value={tmc_inclination_mode}
                            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                        >
                            {#each Object.entries(TMC_INCLINATION_MODES) as [val, label]}
                                <option value={Number(val)}>{label}</option>
                            {/each}
                        </select>
                    </div>
                    <div>
                        <label
                            class="block text-xs text-slate-400 mb-1"
                            for="ts-edm">EDM Mode</label
                        >
                        <select
                            id="ts-edm"
                            bind:value={edm_measurement_mode}
                            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                        >
                            {#each Object.entries(EDM_MEASUREMENT_MODES) as [val, label]}
                                <option value={Number(val)}>{label}</option>
                            {/each}
                        </select>
                    </div>
                    <div>
                        <label
                            class="block text-xs text-slate-400 mb-1"
                            for="ts-prism">Prism Type</label
                        >
                        <select
                            id="ts-prism"
                            bind:value={prism_type}
                            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                        >
                            {#each Object.entries(PRISM_TYPES) as [val, label]}
                                <option value={Number(val)}>{label}</option>
                            {/each}
                        </select>
                    </div>
                </div>

                <!-- Fine Adjust -->
                <h3
                    class="text-xs font-semibold text-slate-500 uppercase tracking-wider pt-2"
                >
                    Fine Adjust
                </h3>
                <div class="grid grid-cols-3 gap-3">
                    <div>
                        <label
                            class="block text-xs text-slate-400 mb-1"
                            for="ts-fapm">Position Mode</label
                        >
                        <select
                            id="ts-fapm"
                            bind:value={fine_adjust_position_mode}
                            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                        >
                            {#each Object.entries(FINE_ADJUST_POSITION_MODES) as [val, label]}
                                <option value={Number(val)}>{label}</option>
                            {/each}
                        </select>
                    </div>
                    <div>
                        <label
                            class="block text-xs text-slate-400 mb-1"
                            for="ts-fahz">Hz Range (rad)</label
                        >
                        <input
                            id="ts-fahz"
                            type="number"
                            step="any"
                            bind:value={fine_adjust_horizontal_search_range}
                            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                        />
                    </div>
                    <div>
                        <label
                            class="block text-xs text-slate-400 mb-1"
                            for="ts-fav">V Range (rad)</label
                        >
                        <input
                            id="ts-fav"
                            type="number"
                            step="any"
                            bind:value={fine_adjust_vertical_search_range}
                            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                        />
                    </div>
                </div>

                <!-- Power Search -->
                <h3
                    class="text-xs font-semibold text-slate-500 uppercase tracking-wider pt-2"
                >
                    Power Search
                </h3>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label
                            class="block text-xs text-slate-400 mb-1"
                            for="ts-pschz">Center Hz (rad)</label
                        >
                        <input
                            id="ts-pschz"
                            type="number"
                            step="any"
                            bind:value={power_search_area_dcenterhz}
                            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                        />
                    </div>
                    <div>
                        <label
                            class="block text-xs text-slate-400 mb-1"
                            for="ts-pscv">Center V (rad)</label
                        >
                        <input
                            id="ts-pscv"
                            type="number"
                            step="any"
                            bind:value={power_search_area_dcenterv}
                            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                        />
                    </div>
                    <div>
                        <label
                            class="block text-xs text-slate-400 mb-1"
                            for="ts-psrhz">Range Hz (rad)</label
                        >
                        <input
                            id="ts-psrhz"
                            type="number"
                            step="any"
                            bind:value={power_search_area_drangehz}
                            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                        />
                    </div>
                    <div>
                        <label
                            class="block text-xs text-slate-400 mb-1"
                            for="ts-psrv">Range V (rad)</label
                        >
                        <input
                            id="ts-psrv"
                            type="number"
                            step="any"
                            bind:value={power_search_area_drangev}
                            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                        />
                    </div>
                    <div>
                        <label
                            class="block text-xs text-slate-400 mb-1"
                            for="ts-pse">Area Enabled</label
                        >
                        <select
                            id="ts-pse"
                            bind:value={power_search_area_enabled}
                            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                        >
                            <option value={1}>Yes</option>
                            <option value={0}>No</option>
                        </select>
                    </div>
                    <div>
                        <label
                            class="block text-xs text-slate-400 mb-1"
                            for="ts-psmin">Min Range (m)</label
                        >
                        <input
                            id="ts-psmin"
                            type="number"
                            bind:value={power_search_min_range}
                            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                        />
                    </div>
                    <div>
                        <label
                            class="block text-xs text-slate-400 mb-1"
                            for="ts-psmax">Max Range (m)</label
                        >
                        <input
                            id="ts-psmax"
                            type="number"
                            bind:value={power_search_max_range}
                            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                        />
                    </div>
                </div>

                <div class="flex items-center gap-3 pt-2">
                    <label
                        class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer"
                    >
                        <input
                            type="checkbox"
                            bind:checked={power_search}
                            class="w-4 h-4 rounded border-slate-600 bg-slate-900 accent-blue-500"
                        />
                        Power Search Enabled
                    </label>
                </div>

                <div class="flex justify-end gap-3 pt-3">
                    <button
                        type="button"
                        onclick={onclose}
                        class="px-4 py-2 text-slate-400 hover:text-white rounded-lg transition-colors cursor-pointer"
                        >Close</button
                    >
                    <button
                        type="submit"
                        disabled={saving}
                        class="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium px-6 py-2 rounded-lg transition-colors cursor-pointer"
                    >
                        {saving ? "Saving..." : "Save"}
                    </button>
                </div>
            </form>
        {/if}
    </div>
</div>
