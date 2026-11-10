/**
 * Connection to the /events websocket of the API.
 *
 * Reconnects automatically with backoff. A watchdog closes the connection if nothing arrives
 * for a while (the server sends a tick every 5 s), so a silently dead connection (e.g. a phone
 * that went to sleep or changed networks) is detected within seconds.
 */
import { eventsUrl } from './api';
import type { ServerEvent } from './types';

type Listener = (event: ServerEvent) => void;
type OpenListener = (reconnect: boolean) => void;

const WATCHDOG_TIMEOUT = 12000;

class EventStream {
    state = $state<'connecting' | 'open' | 'closed'>('connecting');
    /** server clock minus browser clock (s) */
    serverOffset = $state(0);
    lastMessageAt = $state(0);
    version = $state('');

    private ws: WebSocket | null = null;
    private listeners = new Set<Listener>();
    private openListeners = new Set<OpenListener>();
    private sessionId: string | null = null;
    private retry = 0;
    private everOpened = false;
    private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    private watchdog: ReturnType<typeof setInterval> | null = null;

    start(): void {
        if (this.ws) return;
        this.connect();
        this.watchdog = setInterval(() => {
            if (this.state === 'open' && Date.now() - this.lastMessageAt > WATCHDOG_TIMEOUT) {
                this.ws?.close();
            }
        }, 2000);
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible' && this.state !== 'open') this.reconnectNow();
        });
        window.addEventListener('online', () => this.reconnectNow());
    }

    /** Reconnect with a new API URL */
    restart(): void {
        this.ws?.close();
        this.reconnectNow();
    }

    reconnectNow(): void {
        if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
        this.retry = 0;
        if (this.state !== 'open') this.connect();
    }

    private connect(): void {
        if (this.ws && this.ws.readyState <= WebSocket.OPEN) {
            this.ws.onclose = null;
            this.ws.close();
        }
        this.state = 'connecting';
        let ws: WebSocket;
        try {
            ws = new WebSocket(eventsUrl());
        } catch {
            this.scheduleReconnect();
            return;
        }
        this.ws = ws;
        ws.onopen = () => {
            this.state = 'open';
            this.retry = 0;
            this.lastMessageAt = Date.now();
            if (this.sessionId) this.send({ type: 'subscribe', session_id: this.sessionId });
            const reconnect = this.everOpened;
            this.everOpened = true;
            this.openListeners.forEach((fn) => fn(reconnect));
        };
        ws.onmessage = (message) => {
            this.lastMessageAt = Date.now();
            let event: ServerEvent;
            try {
                event = JSON.parse(message.data);
            } catch {
                return;
            }
            if ('server_time' in event && typeof event.server_time === 'number' && (event.type === 'hello' || event.type === 'tick')) {
                this.serverOffset = event.server_time - Date.now() / 1000;
            }
            if (event.type === 'hello') this.version = event.version;
            this.listeners.forEach((fn) => {
                try {
                    fn(event);
                } catch (e) {
                    console.error('Event handler failed', e);
                }
            });
        };
        ws.onclose = () => {
            if (this.ws !== ws) return;
            this.ws = null;
            this.state = 'closed';
            this.scheduleReconnect();
        };
        ws.onerror = () => ws.close();
    }

    private scheduleReconnect(): void {
        if (this.reconnectTimer) return;
        const delay = Math.min(5000, 500 * 2 ** this.retry);
        this.retry++;
        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.connect();
        }, delay);
    }

    send(message: unknown): void {
        if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(message));
    }

    subscribe(sessionId: string | null): void {
        this.sessionId = sessionId;
        this.send({ type: 'subscribe', session_id: sessionId });
    }

    on(fn: Listener): () => void {
        this.listeners.add(fn);
        return () => this.listeners.delete(fn);
    }

    onOpen(fn: OpenListener): () => void {
        this.openListeners.add(fn);
        return () => this.openListeners.delete(fn);
    }

    /** Current time on the server clock (s) */
    serverNow(): number {
        return Date.now() / 1000 + this.serverOffset;
    }
}

export const events = new EventStream();
