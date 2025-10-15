import asyncio
import uuid
from playwright.async_api import async_playwright, expect

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # 1. Register a new user
            await page.goto("http://127.0.0.1:8000")
            await page.get_by_role("button", name="Регистрация").click()

            email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
            password = "password123"

            await page.locator('input[name="email"]').fill(email)
            await page.locator('input[name="password"]').fill(password)
            await page.locator('input[name="confirmPassword"]').fill(password)
            await page.get_by_role("button", name="Создать аккаунт").click()

            # Wait for navigation to the landing page
            await expect(page.get_by_role("heading", name="Neuro D&D")).to_be_visible()

            # 2. Go to settings and take a screenshot
            await page.get_by_role("button", name="Настройки").click()
            await expect(page.get_by_role("heading", name="Настройки")).to_be_visible()

            # Screenshot the sound settings section
            sound_section = page.locator(".bg-black\\/50", has_text="Звук")
            await sound_section.screenshot(path="jules-scratch/verification/settings_audio_final_v5.png")
            print("Screenshot of audio settings saved.")

            # 3. Go to the landing page and take a screenshot of the support button
            await page.get_by_role("button", name="Назад").click()
            await expect(page.get_by_role("heading", name="Neuro D&D")).to_be_visible()
            support_button = page.locator("#supportBtn")
            await support_button.screenshot(path="jules-scratch/verification/support_button_v5.png")
            print("Screenshot of support button saved.")


        except Exception as e:
            print(f"An error occurred: {e}")
            await page.screenshot(path="jules-scratch/verification/error_final_v5.png")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
