/** Tracking settings in the units of the forms (angles in gon); the API stores radians. */
import { units } from './format';
import type { TrackingSettings } from './types';

export const DEFAULT_TRACKING: TrackingSettings = {
    tmc_measurement_mode: 1,
    tmc_inclination_mode: 1,
    edm_measurement_mode: 9,
    prism_type: 3,
    fine_adjust_position_mode: 1,
    fine_adjust_horizontal_search_range: 0.0872,
    fine_adjust_vertical_search_range: 0.0872,
    power_search_area_dcenterhz: 0,
    power_search_area_dcenterv: 1.5708,
    power_search_area_drangehz: 6.283,
    power_search_area_drangev: 0.6,
    power_search_area_enabled: 1,
    power_search_min_range: 1,
    power_search_max_range: 50,
    power_search: true,
};

const ANGLES = [
    'fine_adjust_horizontal_search_range',
    'fine_adjust_vertical_search_range',
    'power_search_area_dcenterhz',
    'power_search_area_dcenterv',
    'power_search_area_drangehz',
    'power_search_area_drangev',
] as const;

export type TrackingForm = Record<string, number | boolean>;

const r4 = (v: number) => Number(v.toFixed(4));

export function trackingToForm(tracking: TrackingSettings | undefined): TrackingForm {
    const form: TrackingForm = { ...(tracking ?? DEFAULT_TRACKING) };
    for (const key of ANGLES) form[key] = r4(units.radToGon(form[key] as number));
    return form;
}

export function trackingFromForm(form: TrackingForm): TrackingSettings {
    const tracking = { ...form };
    for (const key of ANGLES) tracking[key] = units.gonToRad(Number(tracking[key]));
    for (const [key, value] of Object.entries(DEFAULT_TRACKING)) {
        if (typeof value === 'number') tracking[key] = Number(tracking[key]);
    }
    return tracking as unknown as TrackingSettings;
}
