/**
 * A simple wrapper for browser localStorage.
 */
const storage = {
    /**
     * Retrieves the stored user code.
     * @returns {string|null} The user code or null if not found.
     */
    getUserCode() {
        return localStorage.getItem('user_code');
    },

    /**
     * Saves the user code to localStorage.
     * @param {string} code The user code to save.
     */
    saveUserCode(code) {
        localStorage.setItem('user_code', code);
    },

    /**
     * Removes the user code from localStorage.
     */
    removeUserCode() {
        localStorage.removeItem('user_code');
    },

    /**
     * Retrieves a generic item from localStorage.
     * @param {string} key The key of the item to retrieve.
     * @returns {string|null} The value of the item or null.
     */
    getItem(key) {
        return localStorage.getItem(key);
    },

    /**
     * Saves a generic item to localStorage.
     * @param {string} key The key of the item to save.
     * @param {string} value The value of the item to save.
     */
    setItem(key, value) {
        localStorage.setItem(key, value);
    },
};

// Make it available for import in other scripts if using modules,
// or as a global object if not. For this project, it will be a global.
window.appStorage = storage;
