/**
 * Simple internationalization module.
 */
const i18n = {
    // Default language
    currentLanguage: 'en',

    // Language dictionaries
    translations: {
        en: {
            "register_title": "Register",
            "login_title": "Login",
            "username_label": "Username",
            "email_label": "Email",
            "password_label": "Password",
            "register_button": "Register",
            "login_button": "Login",
            "switch_to_login": "Already have an account? Login",
            "switch_to_register": "Don't have an account? Register",
            "logout_button": "Logout",
            "create_campaign_button": "Create Campaign",
            "campaign_name_label": "Campaign Name",
            "campaign_tone_label": "Tone",
            "campaign_difficulty_label": "Difficulty",
            "start_campaign_button": "Start Campaign",
            "welcome_message": "Welcome to Neuro D&D",
            "send_action_button": "Send",
            "action_placeholder": "What do you do?",
            "save_checkpoint_button": "Save Checkpoint",
            "or": "or",
            "epic_fantasy": "Epic Fantasy",
            "cosmic_horror": "Cosmic Horror",
            "noir_detective": "Noir Detective",
            "easy": "Easy",
            "medium": "Medium",
            "hard": "Hard",
        },
        ru: {
            "register_title": "Регистрация",
            "login_title": "Вход",
            "username_label": "Имя пользователя",
            "email_label": "Электронная почта",
            "password_label": "Пароль",
            "register_button": "Зарегистрироваться",
            "login_button": "Войти",
            "switch_to_login": "Уже есть аккаунт? Войти",
            "switch_to_register": "Нет аккаунта? Зарегистрироваться",
            "logout_button": "Выйти",
            "create_campaign_button": "Создать кампанию",
            "campaign_name_label": "Название кампании",
            "campaign_tone_label": "Тон",
            "campaign_difficulty_label": "Сложность",
            "start_campaign_button": "Начать кампанию",
            "welcome_message": "Добро пожаловать в Neuro D&D",
            "send_action_button": "Отправить",
            "action_placeholder": "Что вы делаете?",
            "save_checkpoint_button": "Сохранить",
            "or": "или",
            "epic_fantasy": "Эпическое фэнтези",
            "cosmic_horror": "Космический ужас",
            "noir_detective": "Нуарный детектив",
            "easy": "Легко",
            "medium": "Средне",
            "hard": "Сложно",
        }
    },

    /**
     * Sets the current language.
     * @param {string} lang 'en' or 'ru'.
     */
    setLanguage(lang) {
        if (this.translations[lang]) {
            this.currentLanguage = lang;
            window.appStorage.setItem('language', lang);
            console.log(`Language set to: ${lang}`);
        }
    },

    /**
     * Initializes the language from localStorage or defaults to 'en'.
     */
    init() {
        const savedLang = window.appStorage.getItem('language');
        if (savedLang && this.translations[savedLang]) {
            this.currentLanguage = savedLang;
        } else {
            this.setLanguage('en'); // Default language
        }
    },

    /**
     * Gets the translated string for a given key.
     * @param {string} key The key to translate.
     * @returns {string} The translated string or the key itself if not found.
     */
    t(key) {
        return this.translations[this.currentLanguage][key] || key;
    }
};

// Initialize and expose globally
i18n.init();
window.i18n = i18n;
window.t = (key) => i18n.t(key); // Create a global shortcut function `t()`
