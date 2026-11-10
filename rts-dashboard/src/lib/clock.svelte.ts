/** A shared clock that ticks every second (ages, "x s ago"), on the server time base. */
import { events } from './events.svelte';

class Clock {
    /** Browser time in seconds, updated every second */
    now = $state(Date.now() / 1000);

    constructor() {
        setInterval(() => (this.now = Date.now() / 1000), 1000);
    }

    /** Server time in seconds */
    get server(): number {
        return this.now + events.serverOffset;
    }
}

export const clock = new Clock();
