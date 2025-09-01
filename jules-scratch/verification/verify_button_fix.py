import asyncio
from playwright.async_api import async_playwright, expect

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Base URL for the running application
            base_url = "http://localhost:8000"

            # Go to the registration page first
            await page.goto(f"{base_url}/", timeout=10000)

            # The default language is Russian, so we expect the login button text to be "Войти"
            # This also serves as a good check that the page is loaded.
            await expect(page.locator('[data-action="go:login"]:has-text("Войти")')).to_be_visible()

            # Use data-action for robust selection
            await page.locator('[data-action="go:register"]').click()

            # Wait for registration form to be visible, using Russian text
            await expect(page.locator('h2:has-text("Регистрация")')).to_be_visible()

            # Register a new user to ensure a clean state
            import time
            email = f"testuser_{int(time.time())}@example.com"
            password = "password123"

            await page.locator('input[name="email"]').fill(email)
            await page.locator('input[name="password"]').fill(password)
            await page.locator('input[name="confirmPassword"]').fill(password)

            # The button text is "Создать аккаунт"
            await page.locator('button[type="submit"]:has-text("Создать аккаунт")').click()

            # After registration, we should land on the main page, logged in.
            # Let's verify by looking for the profile button, text "Профиль"
            await expect(page.locator('[data-action="go:profile"]:has-text("Профиль")')).to_be_visible(timeout=10000)

            # Now, perform the navigation test to check for "sticky buttons"
            # 1. Go to Profile page
            await page.locator('[data-action="go:profile"]').click()
            # The profile page h2 will contain the username, but the button to change username will have Russian text
            await expect(page.locator('[data-action="change-username"]:has-text("Изменить ник")')).to_be_visible()

            # 2. Go back to Landing page using the "back" button
            await page.locator('[data-action="go:landing"]').click()
            # The landing page h2 has "AI" in it, which is language-independent
            await expect(page.locator('h2:has-text("AI")')).to_be_visible()

            # 3. Click "New Game". This is the crucial test. Text is "Новая игра"
            await page.locator('button[data-action="go:new-game"]:has-text("Новая игра")').click()

            # 4. Assert we are on the "New Game" page. Text is "Новая игра"
            await expect(page.locator('h2:has-text("Новая игра")')).to_be_visible()

            # 5. Take a screenshot for visual confirmation
            screenshot_path = "jules-scratch/verification/verification.png"
            await page.screenshot(path=screenshot_path)
            print(f"Screenshot saved to {screenshot_path}")

        except Exception as e:
            print(f"An error occurred: {e}")
            await page.screenshot(path="jules-scratch/verification/error.png")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
