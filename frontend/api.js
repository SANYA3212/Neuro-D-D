/**
 * A wrapper for the Fetch API to interact with the backend.
 */
const api = {
    BASE_URL: '/api',

    /**
     * The core fetch function.
     * @param {string} path The endpoint path (e.g., '/auth/login').
     * @param {object} options Standard Fetch API options object.
     * @returns {Promise<any>} The JSON response from the server.
     */
    async fetchJSON(path, options = {}) {
        const url = this.BASE_URL + path;
        const headers = {
            ...options.headers,
        };

        // Get user code and add to headers if it exists
        const userCode = window.appStorage.getUserCode();
        if (userCode) {
            headers['X-User-Code'] = userCode;
        }

        if (options.body) {
            headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(options.body);
        }

        try {
            const response = await fetch(url, { ...options, headers });

            if (!response.ok) {
                // Try to parse error details from the server
                const errorData = await response.json().catch(() => ({ detail: response.statusText }));
                throw new Error(errorData.detail || 'An unknown error occurred.');
            }

            // Handle responses with no content
            if (response.status === 204) {
                return null;
            }

            return response.json();
        } catch (error) {
            console.error('API Fetch Error:', error);
            throw error; // Re-throw the error to be caught by the caller
        }
    },

    // --- Auth ---
    register(username, email, password) {
        return this.fetchJSON('/auth/register', {
            method: 'POST',
            body: { username, email, password },
        });
    },
    login(email, password) {
        return this.fetchJSON('/auth/login', {
            method: 'POST',
            body: { email, password },
        });
    },
    getMe() {
        return this.fetchJSON('/auth/me');
    },

    // --- Users ---
    getSettings() {
        return this.fetchJSON('/users/settings');
    },
    saveSettings(settings) {
        return this.fetchJSON('/users/settings', {
            method: 'PUT',
            body: settings,
        });
    },

    // --- Campaigns ---
    createCampaign(name, tone, difficulty) {
        return this.fetchJSON('/campaigns', {
            method: 'POST',
            body: { name, tone, difficulty },
        });
    },
    getCampaigns() {
        return this.fetchJSON('/campaigns');
    },
    getCampaignDetails(campaignId) {
        return this.fetchJSON(`/campaigns/${campaignId}`);
    },
    addJournalEntry(campaignId, message) {
        return this.fetchJSON(`/campaigns/${campaignId}/journal`, {
            method: 'POST',
            body: { message },
        });
    },
    saveCheckpoint(campaignId) {
        return this.fetchJSON(`/campaigns/${campaignId}/checkpoint`, {
            method: 'POST',
        });
    },

    // --- AI ---
    getAiCompletion(campaignId, messages) {
        return this.fetchJSON('/ai/complete', {
            method: 'POST',
            body: { campaign_id: campaignId, messages: messages },
        });
    },

    // --- Dice ---
    rollDice(sides, seed = null) {
        return this.fetchJSON('/dice/roll', {
            method: 'POST',
            body: { sides, seed },
        });
    },
};

window.api = api;
