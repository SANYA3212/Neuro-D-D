document.addEventListener('DOMContentLoaded', () => {
    // Application state
    const app = {
        currentPage: null,
        currentUser: null,
        currentCampaign: null,
        messageHistory: [],
    };

    // --- DOM Elements ---
    const pages = {
        auth: document.getElementById('page-auth'),
        lobby: document.getElementById('page-lobby'),
        createCampaign: document.getElementById('page-create-campaign'),
        game: document.getElementById('page-game'),
    };

    const forms = {
        login: document.getElementById('login-form'),
        register: document.getElementById('register-form'),
        createCampaign: document.getElementById('create-campaign-form'),
        action: document.getElementById('action-form'),
    };

    const errorMessages = {
        login: document.getElementById('login-error'),
        register: document.getElementById('register-error'),
        createCampaign: document.getElementById('create-campaign-error'),
    };

    // --- Internationalization ---
    function applyTranslations() {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            el.textContent = t(key);
        });
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            el.setAttribute('placeholder', t(key));
        });
        // Also update titles or other attributes if needed
        document.getElementById('auth-title').textContent = t(document.getElementById('login-form').style.display !== 'none' ? 'login_title' : 'register_title');
    }

    // --- Navigation ---
    function navigateTo(pageId) {
        app.currentPage = pageId;
        Object.values(pages).forEach(page => {
            page.classList.toggle('active', page.id === `page-${pageId}`);
        });
        console.log(`Navigated to ${pageId}`);
    }

    // --- Rendering ---
    function renderCampaignList(campaigns) {
        const list = document.getElementById('campaign-list');
        list.innerHTML = '';
        if (campaigns.length === 0) {
            list.innerHTML = `<li>No campaigns found. Create one!</li>`;
            return;
        }
        campaigns.forEach(campaign => {
            const li = document.createElement('li');
            li.textContent = `${campaign.name} (Tone: ${t(campaign.tone)}, Difficulty: ${t(campaign.difficulty)})`;
            li.dataset.campaignId = campaign.id;
            li.addEventListener('click', () => handleSelectCampaign(campaign.id));
            list.appendChild(li);
        });
    }

    function renderJournal() {
        const log = document.getElementById('journal-log');
        log.innerHTML = '';
        app.messageHistory.forEach(msg => {
            const entry = document.createElement('div');
            entry.classList.add('journal-entry');
            entry.innerHTML = `<span class="role-${msg.role}">${msg.role.toUpperCase()}:</span> ${msg.content.replace(/\n/g, '<br>')}`;
            log.appendChild(entry);
        });
        log.scrollTop = log.scrollHeight; // Auto-scroll to bottom
    }

    function displayError(formName, message) {
        const errorEl = errorMessages[formName];
        if (errorEl) {
            errorEl.textContent = message;
            errorEl.style.display = 'block';
        }
    }

    function clearErrors() {
        Object.values(errorMessages).forEach(el => {
            if(el) {
                el.textContent = '';
                el.style.display = 'none';
            }
        });
    }

    // --- Event Handlers ---
    async function handleLogin(event) {
        event.preventDefault();
        clearErrors();
        const email = forms.login.querySelector('#login-email').value;
        const password = forms.login.querySelector('#login-password').value;
        try {
            const { user_code, profile } = await api.login(email, password);
            appStorage.saveUserCode(user_code);
            app.currentUser = profile;
            await loadLobby();
        } catch (error) {
            displayError('login', error.message);
        }
    }

    async function handleRegister(event) {
        event.preventDefault();
        clearErrors();
        const username = forms.register.querySelector('#register-username').value;
        const email = forms.register.querySelector('#register-email').value;
        const password = forms.register.querySelector('#register-password').value;
        try {
            const { user_code, profile } = await api.register(username, email, password);
            appStorage.saveUserCode(user_code);
            app.currentUser = profile;
            await loadLobby();
        } catch (error) {
            displayError('register', error.message);
        }
    }

    function handleLogout() {
        appStorage.removeUserCode();
        app.currentUser = null;
        app.currentCampaign = null;
        navigateTo('auth');
    }

    async function handleCreateCampaign(event) {
        event.preventDefault();
        clearErrors();
        const name = forms.createCampaign.querySelector('#campaign-name').value;
        const tone = forms.createCampaign.querySelector('#campaign-tone').value;
        const difficulty = forms.createCampaign.querySelector('#campaign-difficulty').value;
        try {
            const newCampaign = await api.createCampaign(name, tone, difficulty);
            await loadLobby();
        } catch (error) {
            displayError('createCampaign', error.message);
        }
    }

    async function handleSelectCampaign(campaignId) {
        try {
            const campaignDetails = await api.getCampaignDetails(campaignId);
            app.currentCampaign = campaignDetails.meta;
            app.messageHistory = campaignDetails.journal.entries;
            document.getElementById('game-campaign-name').textContent = app.currentCampaign.name;
            renderJournal();
            navigateTo('game');
        } catch (error) {
            console.error('Failed to load campaign:', error);
        }
    }

    async function handlePlayerAction(event) {
        event.preventDefault();
        const input = document.getElementById('action-input');
        const actionText = input.value.trim();
        if (!actionText) return;

        input.value = ''; // Clear input

        // Add user message to history and render immediately
        const userMessage = { role: 'user', content: actionText };
        app.messageHistory.push(userMessage);
        renderJournal();

        try {
            const aiResponse = await api.getAiCompletion(app.currentCampaign.id, app.messageHistory);

            // Add AI response to history
            const assistantMessage = { role: 'assistant', content: aiResponse.text };
            app.messageHistory.push(assistantMessage);

            // Also add the full message to the server-side journal
            await api.addJournalEntry(app.currentCampaign.id, userMessage);
            await api.addJournalEntry(app.currentCampaign.id, assistantMessage);

            renderJournal();
        } catch (error) {
            console.error('AI completion error:', error);
            const errorMessage = { role: 'system', content: `Error: ${error.message}` };
            app.messageHistory.push(errorMessage);
            renderJournal();
        }
    }

    function handleDiceRoll(event) {
        const sides = parseInt(event.target.dataset.dice, 10);
        if (!sides) return;

        if (sides === 100) {
            const result = dice.rollLocalD100();
            dice.displayRoll(100, result);
        } else {
            const result = dice.rollLocal(sides);
            dice.displayRoll(sides, result);
        }
    }

    // --- Page Loaders ---
    async function loadLobby() {
        try {
            const campaigns = await api.getCampaigns();
            renderCampaignList(campaigns);
            navigateTo('lobby');
        } catch (error) {
            console.error('Failed to load lobby:', error);
            handleLogout(); // If we can't get campaigns, token is likely invalid
        }
    }

    // --- Initialization ---
    function init() {
        // Bind all event listeners
        forms.login.addEventListener('submit', handleLogin);
        forms.register.addEventListener('submit', handleRegister);
        forms.createCampaign.addEventListener('submit', handleCreateCampaign);
        forms.action.addEventListener('submit', handlePlayerAction);

        document.getElementById('logout-btn').addEventListener('click', handleLogout);
        document.getElementById('show-create-campaign-btn').addEventListener('click', () => navigateTo('createCampaign'));
        document.getElementById('back-to-lobby-btn').addEventListener('click', () => navigateTo('lobby'));
        document.getElementById('game-back-to-lobby-btn').addEventListener('click', () => navigateTo('lobby'));

        document.getElementById('switch-to-register-btn').addEventListener('click', () => {
            forms.login.style.display = 'none';
            forms.register.style.display = 'block';
            applyTranslations();
        });
        document.getElementById('switch-to-login-btn').addEventListener('click', () => {
            forms.register.style.display = 'none';
            forms.login.style.display = 'block';
            applyTranslations();
        });

        document.getElementById('dice-tray').addEventListener('click', handleDiceRoll);
        document.getElementById('save-checkpoint-btn').addEventListener('click', () => {
            if(app.currentCampaign) api.saveCheckpoint(app.currentCampaign.id);
        });

        // Language switcher
        document.getElementById('lang-en').addEventListener('click', () => { i18n.setLanguage('en'); applyTranslations(); });
        document.getElementById('lang-ru').addEventListener('click', () => { i18n.setLanguage('ru'); applyTranslations(); });

        // Apply initial translations
        applyTranslations();

        // Check for existing session
        const userCode = appStorage.getUserCode();
        if (userCode) {
            // Validate user code before proceeding
            api.getMe().then(profile => {
                app.currentUser = profile;
                loadLobby();
            }).catch(() => {
                handleLogout(); // Invalid code, clear it
            });
        } else {
            navigateTo('auth');
        }
    }

    init();
});
