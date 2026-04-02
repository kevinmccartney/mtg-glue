import os

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from cli.echo_mtg_to_moxfield import main as run_moxfield_import

load_dotenv()


def main() -> int:
    username = os.environ["ECHOMTG_USERNAME"]
    password = os.environ["ECHOMTG_PASSWORD"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("[1/6] Navigating to login page...")
        page.goto("https://www.echomtg.com/login/")

        print("[2/6] Filling login form...")
        page.fill("input[placeholder='Enter your email']", username)
        page.fill("input[placeholder='Enter your password']", password)
        page.get_by_role("button", name="Sign in").click()

        print("[3/6] Waiting for dashboard...")
        page.wait_for_url("https://www.echomtg.com/dashboard/")
        print(f"      -> landed on: {page.url}")

        print("[4/6] Navigating to collection app...")
        page.goto("https://www.echomtg.com/apps/collection/")
        page.wait_for_load_state("networkidle")

        print("[5/6] Clicking Export to open submenu...")
        page.get_by_role("button", name="Export").click()

        inventory_csv_option = page.locator(
            "div.n-dropdown-option[data-dropdown-option='true']",
            has_text="Inventory CSV",
        )
        inventory_csv_option.wait_for(state="visible")
        print("      -> submenu visible, clicking 'Inventory CSV'...")

        with page.expect_download(timeout=60_000) as download_info:
            inventory_csv_option.click()

        download = download_info.value
        download.save_as(".data/echomtg-export.csv")
        print(f"[6/6] Downloaded: {download.suggested_filename}")

        browser.close()

    print("[7/7] Running Moxfield import pipeline...")
    return run_moxfield_import()


if __name__ == "__main__":
    raise SystemExit(main())
