/**
 * SmartStudy State Manager
 * Shared service for navigation & page state persistence across the platform.
 * Uses sessionStorage for temporary page-level UI state to survive navigation.
 */
const StateManager = (function() {
    'use strict';

    const pageKey = window.location.pathname + window.location.search;

    /**
     * Save a value associated with the current page state.
     */
    function save(key, val) {
        try {
            sessionStorage.setItem(`${pageKey}:${key}`, JSON.stringify(val));
            console.log(`[StateManager] Saved: ${key} =`, val);
        } catch (e) {
            console.error('[StateManager] Failed to save state:', e);
        }
    }

    /**
     * Retrieve a value associated with the current page state.
     */
    function get(key) {
        try {
            const item = sessionStorage.getItem(`${pageKey}:${key}`);
            return item ? JSON.parse(item) : null;
        } catch (e) {
            console.error('[StateManager] Failed to retrieve state:', e);
            return null;
        }
    }

    /**
     * Automatically persist input fields (text, select, checkboxes, radios).
     */
    function autoPersistInputs() {
        const inputs = document.querySelectorAll('input:not([type="password"]):not([type="file"]), select, textarea');
        inputs.forEach(input => {
            const key = input.id || input.name;
            if (!key) return;

            // Exclude dynamically loaded inputs or hidden inputs unless explicitly desired
            if (input.type === 'hidden' || input.classList.contains('no-persist')) return;

            // Restore state
            const savedVal = get(`input:${key}`);
            if (savedVal !== null) {
                if (input.type === 'checkbox') {
                    input.checked = savedVal;
                } else if (input.type === 'radio') {
                    if (input.value === savedVal) {
                        input.checked = true;
                    }
                } else {
                    input.value = savedVal;
                }
                // Trigger change/input events for listeners
                input.dispatchEvent(new Event('change', { bubbles: true }));
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }

            // Save on change/input
            const saveHandler = () => {
                const val = input.type === 'checkbox' ? input.checked : input.value;
                save(`input:${key}`, val);
            };
            input.addEventListener('change', saveHandler);
            input.addEventListener('input', saveHandler);
        });
    }

    /**
     * Automatically persist scroll positions.
     */
    function persistScroll() {
        // Restore window scroll
        const windowScroll = get('scroll:window');
        if (windowScroll) {
            window.scrollTo(windowScroll.x, windowScroll.y);
        }

        // Restore elements with scrollable classes
        const scrollables = document.querySelectorAll('.save-scroll, .study-sidebar, .study-content-panel');
        scrollables.forEach((el, index) => {
            const key = el.id || `scrollable:${index}`;
            const pos = get(`scroll:${key}`);
            if (pos) {
                el.scrollTop = pos.top;
                el.scrollLeft = pos.left;
            }

            el.addEventListener('scroll', () => {
                save(`scroll:${key}`, { top: el.scrollTop, left: el.scrollLeft });
            }, { passive: true });
        });

        window.addEventListener('scroll', () => {
            save('scroll:window', { x: window.scrollX, y: window.scrollY });
        }, { passive: true });
    }

    // Run automatically on page load
    document.addEventListener('DOMContentLoaded', () => {
        autoPersistInputs();
        persistScroll();
    });

    return {
        save: save,
        get: get,
        pageKey: pageKey
    };
})();
window.StateManager = StateManager;
