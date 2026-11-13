<!-- Tracking settings of one station, opened from the Measure page (changed often during a session). -->
<script lang="ts">
    import { api } from '../api';
    import { store } from '../store.svelte';
    import { toast } from '../toast.svelte';
    import { trackingFromForm, trackingToForm, type TrackingForm } from '../tracking';
    import type { RTS } from '../types';
    import TrackingFields from './TrackingFields.svelte';
    import Button from './ui/Button.svelte';
    import Modal from './ui/Modal.svelte';

    let { open = $bindable(false), rts = null }: { open?: boolean; rts?: RTS | null } = $props();

    let form = $state<TrackingForm>(trackingToForm(undefined));
    let busy = $state(false);
    let active = $derived(rts ? store.activeJobsOf(rts.id).length > 0 : false);

    $effect(() => {
        if (open && rts) form = trackingToForm(rts.tracking);
    });

    async function save() {
        if (!rts) return;
        busy = true;
        try {
            await api.updateRts(rts.id, { tracking: trackingFromForm(form) });
            store.rts = await api.rtsList(store.session!.id);
            toast.ok(active ? `${rts.name}: saved, used from the next start` : `${rts.name}: tracking settings saved`);
            open = false;
        } catch (e) {
            toast.error((e as Error).message);
        } finally {
            busy = false;
        }
    }
</script>

<Modal bind:open title={rts ? `Tracking settings · ${rts.name}` : 'Tracking settings'} wide>
    {#if active}
        <p class="mb-4 rounded-[5px] bg-surface-2 px-3 py-2 text-[13px] text-muted">
            {rts?.name} is busy. The running measurement keeps the settings it started with; changes apply from the next start.
        </p>
    {/if}
    <TrackingFields bind:tracking={form} />

    {#snippet footer()}
        <Button onclick={() => (open = false)}>Cancel</Button>
        <Button variant="primary" {busy} onclick={save}>Save</Button>
    {/snippet}
</Modal>
