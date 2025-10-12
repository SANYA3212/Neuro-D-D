from playwright.sync_api import sync_playwright, expect
import random
import time

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = browser.new_page()

    email = f"final_verify_3_{random.randint(1000, 9999)}@example.com"
    password = "password123"

    try:
        # Go to landing page, which will redirect to login
        page.goto("http://127.0.0.1:8000/")
        page.wait_for_load_state('networkidle')

        # Click button to go to registration page from login page
        page.click("#goRegister")

        # Now on registration page, fill form
        expect(page.get_by_label("Email")).to_be_visible(timeout=5000)
        page.get_by_label("Email").fill(email)
        page.get_by_label("Пароль").fill(password)
        page.get_by_label("Подтвердите пароль").fill(password)
        page.get_by_role("button", name="Создать аккаунт").click()

        # Create a game
        expect(page.get_by_role("button", name="Новая игра")).to_be_visible(timeout=10000)
        page.get_by_role("button", name="Новая игра").click()

        expect(page.get_by_placeholder("Название кампании")).to_be_visible()
        page.get_by_placeholder("Название кампании").fill("Test Campaign for Verification")
        page.get_by_role("button", name="Создать комнату").click()

        # Start the game from lobby
        expect(page.get_by_text("Код комнаты:")).to_be_visible(timeout=10000)
        page.get_by_role("button", name="Не готов").click()

        start_game_button = page.get_by_role("button", name="Начать игру")
        expect(start_game_button).to_be_enabled()
        start_game_button.click()

        # On game screen, open dice modal
        expect(page.get_by_placeholder("Введите действие...")).to_be_visible(timeout=10000)
        page.get_by_role("button", name="Бросить куб").click()

        # Screenshot 1: Dice modal is open
        expect(page.get_by_text("d20")).to_be_visible()
        page.screenshot(path="jules-scratch/verification/01_dice_modal.png")

        # Roll a d20
        page.get_by_role("button", name="d20").click()
        expect(page.get_by_text("Вы бросили d20")).to_be_visible()

        # Screenshot 2: Dice roll result
        page.screenshot(path="jules-scratch/verification/02_dice_result.png")

        # Close modal and enter action
        page.get_by_role("button", name="Отмена").click()
        page.get_by_placeholder("Введите действие...").fill("Я осматриваю комнату")

        # Click Ready
        page.get_by_role("button", name="Готов").click()

        # Screenshot 3: Player is ready, host can send turn
        send_turn_button = page.get_by_role("button", name="Отправить ход нейросети (1/1)")
        expect(send_turn_button).to_be_enabled()
        page.screenshot(path="jules-scratch/verification/03_player_ready.png")

        print("All verification steps completed and screenshots saved.")

    except Exception as e:
        print(f"An error occurred: {e}")
        page.screenshot(path="jules-scratch/verification/error.png")
        print("Error screenshot saved to jules-scratch/verification/error.png")

    finally:
        browser.close()

with sync_playwright() as playwright:
    run(playwright)
