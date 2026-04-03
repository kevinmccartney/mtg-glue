import csv
import io
import os
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import boto3
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from cli.echo_mtg_to_moxfield import main as run_moxfield_import

load_dotenv()

EXPORT_PATH = Path(".data/echomtg-export.csv")
OUT_DIR = Path(".out")

# Fields that uniquely identify a card line in the Moxfield CSV.
_CARD_KEY_FIELDS = (
    "Name",
    "Edition",
    "Collector Number",
    "Foil",
    "Language",
    "Condition",
)

CardCounts = dict[tuple, int]


def _boto_client(service: str) -> Any:
    return boto3.Session(region_name=os.environ["AWS_REGION"]).client(service)  # type: ignore[call-overload] # pylint: disable=line-too-long # noqa: E501


def upload_to_s3(bucket: str, local_path: Path, s3_key: str) -> None:
    s3 = _boto_client("s3")
    s3.upload_file(str(local_path), bucket, s3_key)
    print(f"      -> s3://{bucket}/{s3_key}")


def send_notification(sender: str, recipient: str, subject: str, body: str) -> None:
    ses = _boto_client("ses")
    ses.send_email(
        Source=sender,
        Destination={"ToAddresses": [recipient]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": body}},
        },
    )
    print(f"      -> notification sent to {recipient}")


def _parse_card_counts(csv_text: str) -> CardCounts:
    counts: CardCounts = defaultdict(int)
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        key = tuple(row.get(f, "") for f in _CARD_KEY_FIELDS)
        try:
            counts[key] += int(row.get("Count") or 0)
        except ValueError:
            pass
    return dict(counts)


def _fetch_previous_moxfield_csv(bucket: str) -> Optional[tuple[str, str]]:
    """Return (s3_key, csv_text) for the most recent moxfield export, or None."""
    s3 = _boto_client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix="moxfield/"):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])

    if not keys:
        return None

    latest_key = sorted(keys)[-1]
    response = s3.get_object(Bucket=bucket, Key=latest_key)
    csv_text = response["Body"].read().decode("utf-8")
    return latest_key, csv_text


def _build_diff(old_counts: CardCounts, new_counts: CardCounts, prev_key: str) -> str:
    prev_timestamp = prev_key.removeprefix("moxfield/moxfield-import-").removesuffix(
        ".csv"
    )

    all_keys = set(old_counts) | set(new_counts)
    added, removed, changed = [], [], []

    for key in sorted(all_keys):
        name, edition, collector_number, foil, language, condition = key
        label = f"{name} ({edition or '?'}) #{collector_number}" + (
            f" [{foil}]" if foil else ""
        )
        old_qty = old_counts.get(key, 0)
        new_qty = new_counts.get(key, 0)

        if old_qty == 0:
            added.append(f"  + {label} x{new_qty}")
        elif new_qty == 0:
            removed.append(f"  - {label} x{old_qty}")
        elif old_qty != new_qty:
            changed.append(f"  ~ {label}: {old_qty} -> {new_qty}")

    lines = [f"Diff vs {prev_timestamp}:"]
    if not (added or removed or changed):
        lines.append("  No changes.")
        return "\n".join(lines)

    if added:
        lines.append(f"\nAdded ({len(added)}):")
        lines.extend(added)
    if removed:
        lines.append(f"\nRemoved ({len(removed)}):")
        lines.extend(removed)
    if changed:
        lines.append(f"\nChanged ({len(changed)}):")
        lines.extend(changed)

    return "\n".join(lines)


def _run(username: str, password: str, s3_bucket: str, timestamp: str) -> str:
    """Run the full sync and return a success summary string."""
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
        download.save_as(str(EXPORT_PATH))
        print(f"[6/6] Downloaded: {download.suggested_filename}")

        browser.close()

    echomtg_key = f"echomtg/echomtg-export-{timestamp}.csv"
    moxfield_key = f"moxfield/moxfield-import-{timestamp}.csv"

    print(f"[7/9] Uploading EchoMTG export to s3://{s3_bucket}/echomtg/...")
    upload_to_s3(s3_bucket, EXPORT_PATH, echomtg_key)

    print("[8/9] Running Moxfield import pipeline...")
    exit_code = run_moxfield_import()
    if exit_code != 0:
        raise RuntimeError("Moxfield import pipeline exited with a non-zero status.")

    moxfield_csv = OUT_DIR / "moxfield-import.csv"
    new_csv_text = moxfield_csv.read_text(encoding="utf-8")

    print("[9/9] Computing diff against previous export...")
    previous = _fetch_previous_moxfield_csv(s3_bucket)
    if previous:
        prev_key, prev_csv_text = previous
        print(f"      -> comparing against {prev_key}")
        diff_text = _build_diff(
            _parse_card_counts(prev_csv_text),
            _parse_card_counts(new_csv_text),
            prev_key,
        )
        print(diff_text)
    else:
        print("      -> no previous export found, skipping diff")
        diff_text = "No previous export found — this is the first sync."

    print(f"[10/10] Uploading Moxfield import to s3://{s3_bucket}/moxfield/...")
    upload_to_s3(s3_bucket, moxfield_csv, moxfield_key)

    return (
        f"Sync completed at {timestamp} (UTC).\n\n"
        f"Uploaded files:\n"
        f"  s3://{s3_bucket}/{echomtg_key}\n"
        f"  s3://{s3_bucket}/{moxfield_key}\n\n"
        f"{diff_text}\n"
    )


def main() -> int:
    username = os.environ["ECHOMTG_USERNAME"]
    password = os.environ["ECHOMTG_PASSWORD"]
    s3_bucket = os.environ["S3_BUCKET"]
    notification_sender = os.environ["NOTIFICATION_SENDER_EMAIL"]
    notification_recipient = os.environ["NOTIFICATION_RECIPIENT_EMAIL"]

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H:%M:%S")

    try:
        summary = _run(username, password, s3_bucket, timestamp)
        print("[done] Sending success notification...")
        send_notification(
            notification_sender,
            notification_recipient,
            "MTG Glue sync succeeded",
            summary,
        )
        return 0
    except Exception as exc:
        error_body = (
            f"Sync failed at {timestamp} (UTC).\n\n"
            f"Error: {exc}\n\n"
            f"{traceback.format_exc()}"
        )
        print(f"[error] {exc}")
        print("[done] Sending failure notification...")
        send_notification(
            notification_sender,
            notification_recipient,
            "MTG Glue sync FAILED",
            error_body,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
