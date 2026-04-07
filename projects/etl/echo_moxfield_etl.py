import json
import os
import re
import shutil
import tempfile
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from cli.echo_mtg_to_moxfield import convert_echo_export_to_moxfield
from dotenv import load_dotenv
from lib.config import load_etl_runtime_config
from lib.diff import format_moxfield_export_vs_import_diff
from lib.log_config import configure_logging, set_workload
from lib.s3 import boto_client, retain_newest_by_key_prefix, upload_file_to_s3
from loguru import logger
from playwright.sync_api import sync_playwright

load_dotenv()

EXPORT_PATH = Path(".data/echomtg-export.csv")
OUT_DIR = Path(".out")
CONFIG_DOWNLOAD_PATH = Path("config.yaml")


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _s3_csv_retention_count() -> int:
    raw = os.environ.get("S3_CSV_RETENTION_COUNT", "").strip()
    if not raw:
        return 20
    try:
        n = int(raw)
    except ValueError as exc:
        raise ValueError(
            f"S3_CSV_RETENTION_COUNT must be a non-negative integer, got {raw!r}"
        ) from exc
    if n < 0:
        raise ValueError("S3_CSV_RETENTION_COUNT must be non-negative")
    return n


def _trim_timestamped_export_csvs(bucket: str) -> None:
    """Keep the newest N objects per export family; see S3_CSV_RETENTION_COUNT."""
    keep = _s3_csv_retention_count()
    if keep <= 0:
        return
    families = (
        "echomtg/echomtg-export-",
        "moxfield/moxfield-import-",
        "moxfield/moxfield-collection-export-",
    )
    for prefix in families:
        removed = retain_newest_by_key_prefix(bucket, prefix, keep)
        if removed:
            logger.debug(
                "S3 retention: deleted {} older object(s) matching {}*.csv",
                removed,
                prefix,
            )


def send_notification(sender: str, recipient: str, subject: str, body: str) -> None:
    ses = boto_client("ses")
    ses.send_email(
        Source=sender,
        Destination={"ToAddresses": [recipient]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": body}},
        },
    )
    logger.debug("Notification sent to {}", recipient)


def _capsolver_extension_dir() -> Path:
    return Path(os.environ.get("CAPSOLVER_EXTENSION_PATH", "/opt/capsolver-extension"))


def _wait_and_click_moxfield_sign_in(page: Any, timeout_s: float = 120.0) -> None:
    """Wait for a visible, enabled Sign In button, then click it.

    Moxfield can render more than one node that matches the label; the first in
    document order may stay ``disabled`` while the real form button is enabled.
    A single ``.find()`` on the first match then blocks forever.
    """
    sign_in = page.get_by_role("button", name=re.compile(r"^sign in$", re.I))
    sign_in.first.wait_for(state="visible", timeout=30_000)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        n = sign_in.count()
        for i in range(n):
            btn = sign_in.nth(i)
            if btn.is_visible() and btn.is_enabled():
                page.screenshot(path=".data/debug-moxfield-08-pre-sign-in.png")
                btn.click()
                return
        page.wait_for_timeout(200)
    raise TimeoutError("Moxfield Sign In did not become enabled")


def _patch_capsolver_extension_config(api_key: str) -> None:
    """Write CapSolver API key into the unpacked extension's assets/config.js."""
    config_path = _capsolver_extension_dir() / "assets" / "config.js"
    if not config_path.is_file():
        raise FileNotFoundError(
            f"CapSolver extension not found at {config_path}. "
            "Set CAPSOLVER_EXTENSION_PATH or use the Docker image."
        )
    text = config_path.read_text(encoding="utf-8")
    text = re.sub(
        r"apiKey:\s*'[^']*'",
        f"apiKey: {json.dumps(api_key)}",
        text,
        count=1,
    )
    # Solve after username/password so Turnstile tokens stay fresh (extension v1.16+).
    text = re.sub(
        r"manualSolving:\s*\w+",
        "manualSolving: true",
        text,
        count=1,
    )
    config_path.write_text(text, encoding="utf-8")


def _collect_moxfield_import_errors(page: Any) -> list[str]:
    """Expand the import error panel if present and return one string per row error."""
    danger = page.locator("div.alert.alert-danger").filter(
        has_text=re.compile(r"Errors found during import", re.I)
    )
    if danger.count() == 0:
        return []
    details = danger.first.locator("details")
    if details.count() == 0:
        return []
    d0 = details.first
    if d0.get_attribute("open") is None:
        d0.locator("summary").click()
    container = d0.locator("div.pt-3.ps-3")
    container.wait_for(state="visible", timeout=15_000)
    errors: list[str] = []
    for row in container.locator("> div").all():
        text = row.inner_text().strip()
        if text:
            errors.append(text)
    return errors


def _wait_for_completed_download_file(
    downloads_dir: Path,
    seen_before: set[Path],
    timeout_s: float,
) -> Path:
    """
    Poll for a new file in downloads_dir until size is stable
    (Chrome .crdownload finished).
    """
    deadline = time.monotonic() + timeout_s
    poll_s = 0.25
    while time.monotonic() < deadline:
        try:
            entries = list(downloads_dir.iterdir())
        except OSError:
            time.sleep(poll_s)
            continue
        entries.sort(
            key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True
        )
        for path in entries:
            if path.name.endswith(".crdownload") or path.name.endswith(".tmp"):
                continue
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved in seen_before:
                continue
            try:
                sz1 = path.stat().st_size
            except OSError:
                continue
            if sz1 == 0:
                continue
            time.sleep(poll_s * 2)
            try:
                sz2 = path.stat().st_size
            except OSError:
                continue
            if sz1 == sz2:
                return resolved
        time.sleep(poll_s)
    raise TimeoutError(
        f"No new download file in {downloads_dir} within {timeout_s:.0f}s"
    )


@dataclass(frozen=True)
class _MoxfieldCapsolverSession:
    context: Any
    page: Any
    downloads_dir: Path


@contextmanager
def _moxfield_capsolver_browser(
    playwright: Any, api_key: str
) -> Iterator[_MoxfieldCapsolverSession]:
    """Launch Chromium with CapSolver extension; close context and remove temp dirs."""
    _patch_capsolver_extension_config(api_key)
    ext = str(_capsolver_extension_dir().resolve())
    user_data = tempfile.mkdtemp(prefix="pw-capsolver-")
    downloads_dir = Path(tempfile.mkdtemp(prefix="pw-moxfield-dl-"))
    context: Any = None
    try:
        context = playwright.chromium.launch_persistent_context(
            user_data,
            headless=False,
            downloads_path=str(downloads_dir),
            args=[
                f"--disable-extensions-except={ext}",
                f"--load-extension={ext}",
                "--lang=en-US",
            ],
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            ),
        )
        page = context.pages[0] if context.pages else context.new_page()
        yield _MoxfieldCapsolverSession(
            context=context, page=page, downloads_dir=downloads_dir
        )
    finally:
        if context is not None:
            context.close()
        shutil.rmtree(user_data, ignore_errors=True)
        shutil.rmtree(downloads_dir, ignore_errors=True)


def _moxfield_maincontent_more_link(page: Any) -> Any:
    return page.locator("#maincontent a").filter(has_text=re.compile(r"^More$"))


def _moxfield_expose_capsolver_callback(page: Any) -> None:
    def _on_captcha_solved() -> None:
        logger.debug("CapSolver: Captcha solved")

    page.expose_function("captchaSolvedCallback", _on_captcha_solved)


def _moxfield_navigate_to_signin(page: Any) -> None:
    logger.debug("Navigating to Moxfield sign-in...")
    page.goto("https://moxfield.com/account/signin?redirect=/collection")
    page.wait_for_load_state("domcontentloaded")
    page.screenshot(path=".data/debug-moxfield-01-page-load.png")


def _moxfield_wait_login_form(page: Any) -> None:
    logger.debug("Waiting for Moxfield login form...")
    page.locator("input#username").wait_for(state="visible", timeout=30_000)
    page.screenshot(path=".data/debug-moxfield-02-login-form.png")


def _moxfield_fill_credentials(page: Any, username: str, password: str) -> None:
    page.locator("input#username").fill(username)
    page.locator("input#password").fill(password)
    page.screenshot(path=".data/debug-moxfield-03-credentials-filled.png")
    logger.debug("Moxfield Credentials filled")


def _moxfield_submit_sign_in(page: Any) -> None:
    logger.debug("Waiting for Moxfield Sign In to enable...")
    _wait_and_click_moxfield_sign_in(page)


def _moxfield_wait_collection_page(page: Any) -> None:
    logger.debug("Waiting for Moxfield collection URL...")
    page.wait_for_url(
        re.compile(r"https://(www\.)?moxfield\.com/collection/?(\?.*)?(#.*)?$"),
        timeout=60_000,
    )
    logger.debug(f"Landed on: {page.url}")


def _moxfield_export_csv_menu_link(page: Any) -> Any:
    return page.locator(".dropdown-menu a.dropdown-item").filter(
        has_text=re.compile(r"^Export CSV$")
    )


def _moxfield_export_collection_to_path(
    page: Any, downloads_dir: Path, moxfield_export_path: Path
) -> None:
    moxfield_export_path.parent.mkdir(parents=True, exist_ok=True)

    logger.debug('Waiting for #maincontent a "More"...')
    more = _moxfield_maincontent_more_link(page)
    more.wait_for(state="visible", timeout=30_000)
    page.screenshot(path=".data/debug-moxfield-09-collection-more.png")
    more.click()

    logger.debug("Exporting collection CSV (before delete)...")
    export_link = _moxfield_export_csv_menu_link(page)
    export_link.wait_for(state="visible", timeout=15_000)
    seen_downloads = {p.resolve() for p in downloads_dir.iterdir()}
    export_link.click()
    logger.debug("Waiting for export file in downloads directory...")
    finished = _wait_for_completed_download_file(
        downloads_dir, seen_downloads, timeout_s=120.0
    )
    shutil.copy2(finished, moxfield_export_path)
    logger.debug(
        f"Saved Moxfield collection export ({finished.name} → "
        f"{moxfield_export_path.name})"
    )


def _moxfield_delete_entire_collection(page: Any) -> None:
    logger.debug("Opening More → Delete Entire Collection...")
    more = _moxfield_maincontent_more_link(page)
    more.wait_for(state="visible", timeout=30_000)
    more.click()

    logger.debug("Choosing Delete Entire Collection...")
    delete_item = page.locator(".dropdown-menu a.dropdown-item").filter(
        has_text=re.compile(r"^Delete Entire Collection$")
    )
    delete_item.wait_for(state="visible", timeout=15_000)
    delete_item.click()

    logger.debug("Confirming delete modal...")
    confirm_input = page.locator(".modal-content input")
    confirm_input.wait_for(state="visible", timeout=30_000)
    confirm_input.fill("ENTIRE")
    page.screenshot(path=".data/debug-moxfield-10-delete-modal.png")

    delete_btn = page.locator(".modal-footer button").filter(
        has_text=re.compile(r"^Permanently Delete$")
    )
    delete_btn.wait_for(state="visible", timeout=15_000)
    delete_btn.click()
    logger.debug("Submitted Permanently Delete request")


def _moxfield_import_csv_via_ui(page: Any, moxfield_csv_path: Path) -> None:
    if not moxfield_csv_path.is_file():
        raise FileNotFoundError(
            f"Moxfield import CSV not found: {moxfield_csv_path.resolve()}"
        )

    logger.debug("Opening More → Import CSV...")
    more = _moxfield_maincontent_more_link(page)
    more.wait_for(state="visible", timeout=120_000)
    more.click()
    import_link = page.locator(".dropdown-menu a.dropdown-item").filter(
        has_text=re.compile(r"^Import CSV$")
    )
    import_link.wait_for(state="visible", timeout=15_000)
    import_link.click()

    logger.debug("Uploading import CSV...")
    file_input = page.locator("input#filename")
    file_input.wait_for(state="attached", timeout=30_000)
    file_input.set_input_files(str(moxfield_csv_path.resolve()))
    page.screenshot(path=".data/debug-moxfield-11-import-modal.png")

    submit_btn = page.locator(".modal-footer button").filter(
        has_text=re.compile(r"^Import$")
    )
    submit_btn.wait_for(state="visible", timeout=15_000)
    submit_modal = page.locator("div.modal").filter(has=page.locator("input#filename"))
    submit_btn.click()

    logger.debug("Waiting for import modal to close...")
    submit_modal.wait_for(state="hidden", timeout=300_000)

    logger.debug("Waiting for import success alert...")
    page.locator(".alert.alert-success").filter(
        has_text=re.compile(r"Successfully imported your collection\.")
    ).wait_for(state="visible", timeout=300_000)
    page.screenshot(path=".data/debug-moxfield-12-import-success.png")
    logger.debug("Collection import completed")


def _moxfield_collect_import_errors_safe(page: Any) -> list[str]:
    try:
        import_errors = _collect_moxfield_import_errors(page)
    except Exception as exc:
        logger.warning("Could not read Moxfield import errors: {}", exc)
        return []
    if import_errors:
        logger.debug(f"Moxfield reported {len(import_errors)} import row error(s)")
        page.screenshot(path=".data/debug-moxfield-13-import-errors.png")
    return import_errors


def _moxfield_login_with_capsolver_extension(
    playwright: Any,
    username: str,
    password: str,
    api_key: str,
    moxfield_csv_path: Path,
    moxfield_export_path: Path,
) -> list[str]:
    """
    Log into Moxfield with the CapSolver Chrome extension (CapSolver + Playwright).
    Export collection CSV, delete collection, import CSV; return import row errors.
    """
    with _moxfield_capsolver_browser(playwright, api_key) as session:
        page = session.page
        _moxfield_expose_capsolver_callback(page)
        _moxfield_navigate_to_signin(page)
        _moxfield_wait_login_form(page)
        _moxfield_fill_credentials(page, username, password)
        _moxfield_submit_sign_in(page)
        _moxfield_wait_collection_page(page)
        logger.info("Backing up Moxfield Collection")
        _moxfield_export_collection_to_path(
            page, session.downloads_dir, moxfield_export_path
        )
        set_workload("MoxfieldCollectionUpdate")
        logger.info("Updating Moxfield Collection")
        _moxfield_delete_entire_collection(page)
        _moxfield_import_csv_via_ui(page, moxfield_csv_path)
        return _moxfield_collect_import_errors_safe(page)


def _run(
    username: str,
    password: str,
    s3_bucket: str,
    timestamp: str,
    moxfield_username: str,
    moxfield_password: str,
    capsolver_api_key: str,
) -> tuple[str, list[str]]:
    """
    Run the full sync; return
    (email body, Moxfield row errors — non-empty means failure).
    """
    set_workload("EchoMTGCollectionExport")
    logger.info("Exporting EchoMTG Collection")
    echo_headed = _env_truthy("ECHO_MTG_HEADED")
    with sync_playwright() as p:
        logger.debug("Launching Chromium for EchoMTG...")
        browser = p.chromium.launch(headless=not echo_headed)
        page = browser.new_page()

        logger.debug("[1/6] Navigating to login page...")
        page.goto("https://www.echomtg.com/login/")

        logger.debug("[2/6] Filling login form...")
        page.fill("input[placeholder='Enter your email']", username)
        page.fill("input[placeholder='Enter your password']", password)
        page.get_by_role("button", name="Sign in").click()

        logger.debug("[3/6] Waiting for dashboard...")
        page.wait_for_url("https://www.echomtg.com/dashboard/")
        logger.debug(f"      -> landed on: {page.url}")

        logger.debug("[4/6] Navigating to collection app...")
        page.goto("https://www.echomtg.com/apps/collection/")
        page.wait_for_load_state("networkidle")

        logger.debug("[5/6] Clicking Export to open submenu...")
        page.get_by_role("button", name="Export").click()

        inventory_csv_option = page.locator(
            "div.n-dropdown-option[data-dropdown-option='true']",
            has_text="Inventory CSV",
        )
        inventory_csv_option.wait_for(state="visible")
        logger.debug("      -> submenu visible, clicking 'Inventory CSV'...")

        with page.expect_download(timeout=60_000) as download_info:
            inventory_csv_option.click()

        download = download_info.value
        download.save_as(str(EXPORT_PATH))
        logger.debug(f"[6/6] Downloaded: {download.suggested_filename}")

        browser.close()

    echomtg_key = f"echomtg/echomtg-export-{timestamp}.csv"
    moxfield_key = f"moxfield/moxfield-import-{timestamp}.csv"
    moxfield_export_key = f"moxfield/moxfield-collection-export-{timestamp}.csv"
    moxfield_export_path = Path(".data") / f"moxfield-collection-export-{timestamp}.csv"

    set_workload("EchoMTGCollectionBackup")
    logger.info("Backing up EchoMTG Collection")
    logger.debug(f"[7/11] Uploading EchoMTG export to s3://{s3_bucket}/echomtg/...")
    upload_file_to_s3(s3_bucket, EXPORT_PATH, echomtg_key)

    set_workload("MoxfieldImportCreate")
    logger.info("Creating Moxfield Import")
    logger.debug("[8/11] Running Moxfield import pipeline (Echo → import CSV)...")
    s3_key = os.environ.get("MTG_GLUE_CONFIG_S3_KEY", "").strip()
    s3_bucket = os.environ.get("S3_BUCKET", "").strip()
    etl_config = load_etl_runtime_config(CONFIG_DOWNLOAD_PATH, s3_bucket, s3_key)
    exit_code = convert_echo_export_to_moxfield(
        etl_config,
        EXPORT_PATH,
        OUT_DIR / "moxfield-import.csv",
    )
    if exit_code != 0:
        raise RuntimeError("Moxfield import pipeline exited with a non-zero status.")

    moxfield_csv = OUT_DIR / "moxfield-import.csv"
    new_csv_text = moxfield_csv.read_text(encoding="utf-8")

    set_workload("MoxfieldImportBackup")
    logger.info("Backing up Moxfield Import")
    logger.debug(f"[9/11] Uploading Moxfield import to s3://{s3_bucket}/moxfield/...")
    upload_file_to_s3(s3_bucket, moxfield_csv, moxfield_key)

    set_workload("MoxfieldCollectionBackup")
    logger.debug("[10/11] Logging into Moxfield (CapSolver extension)...")
    with sync_playwright() as p:
        moxfield_import_errors = _moxfield_login_with_capsolver_extension(
            p,
            moxfield_username,
            moxfield_password,
            capsolver_api_key,
            moxfield_csv,
            moxfield_export_path,
        )

    logger.debug(
        f"[11/11] Uploading Moxfield collection export to s3://{s3_bucket}/moxfield/..."
    )
    upload_file_to_s3(s3_bucket, moxfield_export_path, moxfield_export_key)

    _trim_timestamped_export_csvs(s3_bucket)

    export_vs_import_diff = format_moxfield_export_vs_import_diff(
        moxfield_export_path.read_text(encoding="utf-8"),
        new_csv_text,
        "Diff (pre-sync Moxfield collection export vs this run's import CSV)",
    )
    logger.debug("Diff computed (full text in email only)")

    summary = (
        f"Sync completed at {timestamp} (UTC).\n\n"
        f"Uploaded files:\n"
        f"  s3://{s3_bucket}/{echomtg_key}\n"
        f"  s3://{s3_bucket}/{moxfield_export_key}\n"
        f"  s3://{s3_bucket}/{moxfield_key}\n\n"
        f"{export_vs_import_diff}\n"
    )
    if moxfield_import_errors:
        lines = "\n".join(f"  • {err}" for err in moxfield_import_errors)
        summary += f"\nMoxfield import reported the following row errors:\n{lines}\n"
    return summary, moxfield_import_errors


def main() -> int:
    configure_logging()
    logger.debug("MTG Glue container started")
    set_workload("ETL")
    logger.info("Starting ETL pipeline")
    username = os.environ["ECHOMTG_USERNAME"]
    password = os.environ["ECHOMTG_PASSWORD"]
    s3_bucket = os.environ["S3_BUCKET"]
    notification_sender = os.environ["NOTIFICATION_SENDER_EMAIL"]
    notification_recipient = os.environ["NOTIFICATION_RECIPIENT_EMAIL"]
    moxfield_username = os.environ["MOXFIELD_USERNAME"]
    moxfield_password = os.environ["MOXFIELD_PASSWORD"]
    capsolver_api_key = os.environ["CAPSOLVER_API_KEY"]

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H:%M:%S")

    try:
        summary, moxfield_import_errors = _run(
            username,
            password,
            s3_bucket,
            timestamp,
            moxfield_username,
            moxfield_password,
            capsolver_api_key,
        )
        n_err = len(moxfield_import_errors)
        if n_err:
            logger.error(
                "Moxfield reported {} import row error(s); treating sync as failed.",
                n_err,
            )
            set_workload("ETLNotification")
            logger.info("Sending ETL pipeline status notification")
            subject = (
                f"MTG Glue sync FAILED ({n_err} Moxfield import row "
                f"error{'s' if n_err != 1 else ''})"
            )
            body = (
                "The pipeline finished uploads, but Moxfield reported "
                "row-level import errors (see below).\n\n"
                f"{summary}"
            )
            send_notification(
                notification_sender,
                notification_recipient,
                subject,
                body,
            )
            return 1
        set_workload("ETLNotification")
        logger.info("Sending ETL pipeline status notification")
        send_notification(
            notification_sender,
            notification_recipient,
            "MTG Glue sync succeeded",
            summary,
        )
        logger.info("ETL pipeline succeeded")

        return 0
    except Exception as exc:
        error_body = (
            f"Sync failed at {timestamp} (UTC).\n\n"
            f"Error: {exc}\n\n"
            f"{traceback.format_exc()}"
        )
        logger.error("{}", exc)
        set_workload("ETLNotification")
        logger.info("Sending ETL pipeline status notification")
        send_notification(
            notification_sender,
            notification_recipient,
            "MTG Glue sync FAILED",
            error_body,
        )
        logger.error("ETL pipeline failed")

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
