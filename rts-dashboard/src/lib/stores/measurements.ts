import { writable } from 'svelte/store';
import type { MeasurementResponse } from '../api/types';

const MAX_CACHED = 5000;

function createMeasurementCache() {
    const { subscribe, set, update } = writable<MeasurementResponse[]>([]);

    return {
        subscribe,
        addMeasurements(newMeasurements: MeasurementResponse[]) {
            update((existing) => {
                const existingKeys = new Set(
                    existing.map((m) => `${m.controller_timestamp}:${m.rts_id}`),
                );
                const unique = newMeasurements.filter(
                    (m) => !existingKeys.has(`${m.controller_timestamp}:${m.rts_id}`),
                );
                if (unique.length === 0) return existing;
                const combined = [...existing, ...unique];
                return combined.length > MAX_CACHED
                    ? combined.slice(combined.length - MAX_CACHED)
                    : combined;
            });
        },
        clear() {
            set([]);
        },
    };
}

export const measurementCache = createMeasurementCache();
