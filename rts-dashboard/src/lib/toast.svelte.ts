export interface Toast {
    id: number;
    kind: 'info' | 'ok' | 'error';
    message: string;
}

class Toasts {
    items = $state<Toast[]>([]);
    private next = 1;

    show(kind: Toast['kind'], message: string, timeout = kind === 'error' ? 8000 : 4000): void {
        const id = this.next++;
        this.items = [...this.items.slice(-4), { id, kind, message }];
        setTimeout(() => this.dismiss(id), timeout);
    }

    info(message: string): void {
        this.show('info', message);
    }

    ok(message: string): void {
        this.show('ok', message);
    }

    error(message: string): void {
        this.show('error', message);
    }

    dismiss(id: number): void {
        this.items = this.items.filter((t) => t.id !== id);
    }
}

export const toast = new Toasts();
