/**
 * Client-side dice rolling logic and UI updates.
 */
const dice = {
    /**
     * Rolls a single die with a given number of sides.
     * @param {number} sides The number of sides on the die.
     * @returns {number} The result of the roll.
     */
    rollLocal(sides) {
        if (sides <= 0) return 1;
        return Math.floor(Math.random() * sides) + 1;
    },

    /**
     * Performs a local D100 roll.
     * @returns {object} An object with tens, ones, and the final result.
     */
    rollLocalD100() {
        const tens = Math.floor(Math.random() * 10) * 10;
        const ones = Math.floor(Math.random() * 10);
        let result = tens + ones;
        if (result === 0) {
            result = 100;
        }
        return {
            tens: tens / 10, // show the 0-9 die face
            ones: ones,      // show the 0-9 die face
            result: result,
        };
    },

    /**
     * Displays a dice roll result in the UI.
     * @param {number} sides The type of die rolled (e.g., 20 for a D20).
     * @param {object|number} result The result object (for D100) or number.
     */
    displayRoll(sides, result) {
        const diceTray = document.getElementById('dice-tray-result');
        if (!diceTray) return;

        let displayText = '';
        if (sides === 100 && typeof result === 'object') {
            displayText = `D100: ${result.result} (Tens: ${result.tens}, Ones: ${result.ones})`;
        } else {
            displayText = `D${sides}: ${result}`;
        }

        diceTray.textContent = displayText;

        // Add a simple animation effect
        diceTray.classList.remove('roll-animation');
        // This is a trick to re-trigger the animation
        void diceTray.offsetWidth;
        diceTray.classList.add('roll-animation');
    }
};

window.dice = dice;
