/** Screen size for layouts that CSS alone cannot adapt (plot heights, canvas margins). */

const PHONE = '(max-width: 767px)';

class Media {
    /** Below the md breakpoint of Tailwind (768 px): phones in portrait and landscape */
    phone = $state(false);

    constructor() {
        const query = window.matchMedia(PHONE);
        this.phone = query.matches;
        query.addEventListener('change', (e) => (this.phone = e.matches));
    }
}

export const media = new Media();
