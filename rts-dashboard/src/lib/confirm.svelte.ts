/** Promise based confirmation dialog: `if (await confirm({...})) ...` */

export interface ConfirmOptions {
    title: string;
    message: string;
    confirm?: string;
    danger?: boolean;
}

class ConfirmStore {
    current = $state<(ConfirmOptions & { resolve: (ok: boolean) => void }) | null>(null);

    ask(options: ConfirmOptions): Promise<boolean> {
        this.current?.resolve(false);
        return new Promise((resolve) => {
            this.current = { ...options, resolve };
        });
    }

    answer(ok: boolean): void {
        this.current?.resolve(ok);
        this.current = null;
    }
}

export const confirmStore = new ConfirmStore();
export const confirm = (options: ConfirmOptions) => confirmStore.ask(options);
