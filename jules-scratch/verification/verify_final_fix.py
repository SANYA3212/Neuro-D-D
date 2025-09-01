import asyncio
from playwright.async_api import async_playwright, expect
import time

async def register_user_if_needed(page, base_url, email, password):
    """Navigates to registration and creates a user. Ignores errors if user exists."""
    print("Attempting to register a user for the test...")
    await page.goto(f"{base_url}/")

    await expect(page.locator('h2:has-text("Войти")')).to_be_visible(timeout=10000)
    # Use data-action locator
    await page.locator('[data-action="go:register"]').click()

    await expect(page.locator('h2:has-text("Регистрация")')).to_be_visible()
    await page.locator('input[name="email"]').fill(email)
    await page.locator('input[name="password"]').fill(password)
    await page.locator('input[name="confirmPassword"]').fill(password)
    await page.locator('button[type="submit"]:has-text("Создать аккаунт")').click()

    try:
        await expect(page.locator('[data-action="go:profile"]')).to_be_visible(timeout=5000)
        print("Registration successful and auto-logged in.")
    except Exception:
        print("Registration might have failed (e.g., user exists) or did not auto-login. Proceeding to login.")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        base_url = "http://localhost:8000"
        email = "test.user@example.com"
        password = "password123"

        try:
            await register_user_if_needed(page, base_url, email, password)

            print("Starting login test...")
            await page.goto(f"{base_url}/")

            await expect(page.locator('h2:has-text("Войти")')).to_be_visible(timeout=5000)

            await page.locator('input[name="email"]').fill(email)
            await page.locator('input[name="password"]').fill(password)
            await page.locator('button[type="submit"]:has-text("Войти")').click()

            await expect(page.locator('[data-action="go:profile"]')).to_be_visible(timeout=10000)
            print("Login successful, on landing page.")

            # Use data-action locator
            await page.locator('[data-action="go:new-game"]').click()

            await expect(page.locator('h2:has-text("Новая игра")')).to_be_visible()
            print("Navigation to New Game page successful.")

            screenshot_path = "jules-scratch/verification/final_verification.png"
            await page.screenshot(path=screenshot_path)
            print(f"Screenshot of final fix saved to {screenshot_path}")

        except Exception as e:
            print(f"An error occurred during final verification: {e}")
            await page.screenshot(path="jules-scratch/verification/error_final.png")
        finally:
            await browser.close()

if __name__ == "__main__":
    import subprocess
    import sys

    server_process = None
    try:
        print("Starting server with live logging...")
        server_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"],
        )
        print(f"Server process started with PID: {server_process.pid}")
        time.sleep(5)

        if server_process.poll() is not None:
            print("Server process died immediately. Cannot run tests.")
            exit(1)

        print("Server should be running. Running Playwright script...")
        asyncio.run(main())

    finally:
        if server_process:
            print("Terminating server...")
            server_process.terminate()
            server_process.wait()
            print("Server terminated.")
