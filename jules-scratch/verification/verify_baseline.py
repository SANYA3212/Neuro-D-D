import asyncio
from playwright.async_api import async_playwright, expect
import time

async def register_user_if_needed(page, base_url, email, password):
    """Navigates to registration and creates a user. Ignores errors if user exists."""
    print("Attempting to register a user for the test...")
    await page.goto(f"{base_url}/")

    # On a fresh start, we should be on the login page.
    await expect(page.locator('h2:has-text("Войти")')).to_be_visible(timeout=10000)
    await page.locator('#goRegister').click()

    await expect(page.locator('h2:has-text("Регистрация")')).to_be_visible()
    await page.locator('input[name="email"]').fill(email)
    await page.locator('input[name="password"]').fill(password)
    await page.locator('input[name="confirmPassword"]').fill(password)
    await page.locator('button[type="submit"]:has-text("Создать аккаунт")').click()

    # After registration, we should be on the landing page.
    # If it fails, an error will be thrown, but we'll try to log in anyway.
    try:
        await expect(page.locator('button:has-text("Профиль")')).to_be_visible(timeout=5000)
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
            # First, ensure the user exists. This also logs out any existing session.
            await register_user_if_needed(page, base_url, email, password)

            # Now, perform the actual test login.
            print("Starting login test...")
            await page.goto(f"{base_url}/")

            # We should be on the login page.
            await expect(page.locator('h2:has-text("Войти")')).to_be_visible(timeout=5000)

            # Fill in credentials and log in
            await page.locator('input[name="email"]').fill(email)
            await page.locator('input[name="password"]').fill(password)
            await page.locator('button[type="submit"]:has-text("Войти")').click()

            # Wait for the landing page to load after login
            await expect(page.locator('button:has-text("Профиль")')).to_be_visible(timeout=10000)
            print("Login successful, on landing page.")

            # From the landing page, click the "New Game" button.
            await page.locator('#btnCreateRoom').click()

            # Expect to be on the "New Game" page
            await expect(page.locator('h2:has-text("Новая игра")')).to_be_visible()
            print("Navigation to New Game page successful.")

            # Take a screenshot for visual confirmation
            screenshot_path = "jules-scratch/verification/baseline_verification.png"
            await page.screenshot(path=screenshot_path)
            print(f"Screenshot of baseline saved to {screenshot_path}")

        except Exception as e:
            print(f"An error occurred during baseline verification: {e}")
            await page.screenshot(path="jules-scratch/verification/error.png")
        finally:
            await browser.close()

if __name__ == "__main__":
    import subprocess
    import sys

    server_process = None
    try:
        print("Starting server with live logging...")
        # Run server with stdout/stderr going to the console
        server_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"],
        )
        print(f"Server process started with PID: {server_process.pid}")
        time.sleep(5)

        # A simple check to see if the process died immediately
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
