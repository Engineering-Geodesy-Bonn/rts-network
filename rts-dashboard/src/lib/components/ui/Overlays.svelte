<!-- Global confirmation dialog and toasts -->
<script lang="ts">
    import { confirmStore } from '../../confirm.svelte';
    import { toast } from '../../toast.svelte';
    import Button from './Button.svelte';
    import Icon from './Icon.svelte';
    import Modal from './Modal.svelte';

    let open = $state(false);
    $effect(() => {
        open = confirmStore.current !== null;
    });
</script>

{#if confirmStore.current}
    {@const c = confirmStore.current}
    <Modal bind:open title={c.title} onclose={() => confirmStore.answer(false)}>
        <p class="text-sm leading-relaxed text-muted">{c.message}</p>
        {#snippet footer()}
            <Button onclick={() => confirmStore.answer(false)}>Cancel</Button>
            <Button variant={c.danger ? 'danger' : 'primary'} onclick={() => confirmStore.answer(true)}>{c.confirm ?? 'OK'}</Button>
        {/snippet}
    </Modal>
{/if}

<div class="pointer-events-none fixed inset-x-0 bottom-20 z-[60] flex flex-col items-center gap-2 px-4 md:bottom-6" aria-live="polite">
    {#each toast.items as t (t.id)}
        <div
            class="pointer-events-auto flex max-w-md items-start gap-2.5 rounded-xl border px-4 py-3 text-sm shadow-lg {t.kind === 'error'
                ? 'border-fail/40 bg-fail-bg text-fail'
                : t.kind === 'ok'
                  ? 'border-ok/40 bg-ok-bg text-ok'
                  : 'border-line bg-surface text-fg'}"
        >
            <Icon name={t.kind === 'error' ? 'alert' : t.kind === 'ok' ? 'check' : 'info'} class="mt-0.5" />
            <span class="flex-1 break-words">{t.message}</span>
            <button class="opacity-60 hover:opacity-100" aria-label="Dismiss" onclick={() => toast.dismiss(t.id)}><Icon name="x" size={16} /></button>
        </div>
    {/each}
</div>
