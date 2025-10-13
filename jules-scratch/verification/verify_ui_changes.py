import asyncio
from playwright.async_api import async_playwright, expect
import random

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            # 1. Go to the app and register
            await page.goto("http://localhost:8000")
            await page.get_by_role("button", name="Регистрация").click()
            email = f"testuser_{random.randint(10000, 99999)}@example.com"
            await page.locator('input[name="email"]').fill(email)
            await page.locator('input[name="password"]').fill("password123")
            await page.locator('input[name="confirmPassword"]').fill("password123")
            await page.get_by_role("button", name="Создать аккаунт").click()
            await expect(page.get_by_role("heading", name="Neuro D&D")).to_be_visible()

            # 2. Create and start a game
            await page.get_by_role("button", name="Новая игра").click()
            await page.get_by_placeholder("Название кампании").fill("Тест UI")
            await page.get_by_role("button", name="Создать комнату").click()
            await expect(page.get_by_text("Код комнаты:")).to_be_visible()
            await page.get_by_role("button", name="Не готов").click() # Ready up in lobby
            await page.get_by_role("button", name="Начать игру").click()

            # 3. On game screen, roll a dice
            await expect(page.get_by_role("heading", name="Тест UI")).to_be_visible()
            await page.get_by_role("button", name="Бросить куб").click()
            await expect(page.get_by_role("heading", name="Бросить куб")).to_be_visible()

            # Take a screenshot of the centered dice
            await page.screenshot(path="jules-scratch/verification/centered_dice.png")

            await page.get_by_role("button", name="d20").click()
            # Modal closes automatically, wait for it to be gone
            await expect(page.get_by_role("heading", name="Бросить куб")).not_to_be_visible()

            # 4. Verify dice roll is displayed and input is not disabled
            input_field = page.get_by_placeholder("Введите действие...")
            ready_button = page.get_by_role("button", name="Готов")

            # Look for the dice display container which should now be visible
            dice_display = page.get_by_test_id("dice-roll-display")
            await expect(dice_display).to_be_visible()
            await expect(dice_display).to_contain_text("d20")
            await expect(input_field).not_to_be_disabled()
            await expect(ready_button).not_to_be_disabled()

            # 5. Click "Ready" and verify input is disabled
            await ready_button.click()

            # Give it a moment for the state to update via WebSocket
            await page.wait_for_timeout(500)

            await expect(input_field).to_be_disabled()
            await expect(ready_button).to_be_disabled()

            # 6. Take final screenshot of the disabled state
            await page.screenshot(path="jules-scratch/verification/disabled_input.png")
            print("Screenshots taken successfully.")

        except Exception as e:
            print(f"An error occurred: {e}")
            await page.screenshot(path="jules-scratch/verification/error.png")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
