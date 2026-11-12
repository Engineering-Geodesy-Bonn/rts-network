/** External sensors and the time synchronization, polled while a page that shows them is open. */
import { api } from './api';
import { events } from './events.svelte';
import type { ExternalSensor, SensorTrack, SynchronizerState } from './types';

/** Colors of external sensors in plots (distinct from the station colors) */
const SENSOR_COLORS = ['#d6336c', '#0ca678', '#f08c00', '#845ef7', '#1c7ed6', '#e64980'];

export function sensorColor(index: number): string {
    return SENSOR_COLORS[((index % SENSOR_COLORS.length) + SENSOR_COLORS.length) % SENSOR_COLORS.length];
}

class SensorStore {
    sensors = $state<ExternalSensor[]>([]);
    sync = $state<SynchronizerState | null>(null);
    tracks = $state.raw<SensorTrack[]>([]);
    loaded = $state(false);
    error = $state('');

    private users = 0;
    private trackUsers = 0;
    private timer = 0;
    private tick = 0;
    private offEvents: (() => void) | null = null;

    sensorIndex(id: string | null | undefined): number {
        return this.sensors.findIndex((s) => s.id === id);
    }

    /** Starts polling; returns the function that stops it again. */
    use(withTracks = false): () => void {
        this.users++;
        if (withTracks) this.trackUsers++;
        if (this.users === 1) {
            this.offEvents = events.on((e) => {
                if (e.type === 'changed' && (e.entity === 'external_sensor' || e.entity === 'synchronizer')) void this.refresh(true);
            });
            this.timer = window.setInterval(() => void this.refresh(), 1000);
        }
        void this.refresh(true);
        return () => {
            this.users--;
            if (withTracks) this.trackUsers--;
            if (this.users === 0) {
                clearInterval(this.timer);
                this.offEvents?.();
                this.offEvents = null;
            }
        };
    }

    async refresh(all = false): Promise<void> {
        this.tick++;
        try {
            const [sensors, sync, tracks] = await Promise.all([
                all || this.tick % 2 === 0 ? api.externalSensors() : Promise.resolve(null),
                api.syncState(),
                this.trackUsers > 0 ? api.sensorTracks(120) : Promise.resolve(null),
            ]);
            if (sensors) this.sensors = sensors;
            this.sync = sync;
            if (tracks) this.tracks = tracks;
            this.error = '';
        } catch (e) {
            this.error = (e as Error).message;
        } finally {
            this.loaded = true;
        }
    }
}

export const sensorStore = new SensorStore();
