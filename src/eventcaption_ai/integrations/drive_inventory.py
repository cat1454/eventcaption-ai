"""Read-only Drive metadata inventory. No media/model downloads or GPU calls."""
import argparse
from collections import deque
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import re
import sys
import time
from urllib.parse import urlparse

SCOPE = "https://www.googleapis.com/auth/drive.metadata.readonly"
DEFAULT_FOLDER = "1sOdWrfxWjxr9vQdAaj3fnMxJGChyYS5v"
FOLDER = "application/vnd.google-apps.folder"
SHORTCUT = "application/vnd.google-apps.shortcut"
FIELDS = ("id,name,mimeType,parents,webViewLink,size,modifiedTime,driveId,"
          "md5Checksum,sha1Checksum,sha256Checksum,videoMediaMetadata,shortcutDetails")
CSV_FIELDS = ("id", "name", "webViewLink", "parent_ids", "size_bytes", "modifiedTime",
              "duration_ms", "width", "height", "md5Checksum", "sha1Checksum", "sha256Checksum")


def folder_id(value):
    value = value.strip()
    if value.startswith("https://"):
        parsed = urlparse(value)
        match = re.fullmatch(r"/drive/(?:u/\d+/)?folders/([\w-]+)/?", parsed.path)
        if parsed.hostname != "drive.google.com" or not match:
            raise argparse.ArgumentTypeError("Use a Google Drive folder URL or folder ID")
        value = match.group(1)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise argparse.ArgumentTypeError("Invalid Google Drive folder ID")
    return value


def auth_directory():
    base = Path(os.environ["LOCALAPPDATA"]) if os.environ.get("LOCALAPPDATA") else Path.home() / ".config"
    return base / "EventCaption-AI" / "google-drive"


def create_service(credentials_path, token_path):
    # Imports are optional: --help and CPU inventory tests need no Google packages.
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    import google_auth_httplib2
    import httplib2

    credentials = None
    if token_path.exists():
        info = json.loads(token_path.read_text(encoding="utf-8"))
        if set(info.get("scopes", [])) != {SCOPE}:
            raise ValueError("Use a dedicated token with only drive.metadata.readonly")
        credentials = Credentials.from_authorized_user_info(info, [SCOPE])
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), [SCOPE])
            credentials = flow.run_local_server(host="localhost", port=0, timeout_seconds=300)
        if set(credentials.granted_scopes or credentials.scopes or []) != {SCOPE}:
            raise ValueError("Google did not grant exactly the requested metadata-only scope")
        token_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic token refresh; separate from append-only study/inventory evidence.
        temp = token_path.with_name(token_path.name + ".tmp")
        with temp.open("x", encoding="utf-8") as stream:
            stream.write(credentials.to_json())
        temp.replace(token_path)
    http = google_auth_httplib2.AuthorizedHttp(credentials, http=httplib2.Http(timeout=30))
    return build("drive", "v3", http=http, cache_discovery=False)


def error_details(error):
    """Avoid logging request URLs, OAuth responses, tokens or exception messages."""
    status = getattr(getattr(error, "resp", None), "status", None)
    reasons = []
    try:
        body = json.loads(getattr(error, "content", b"{}"))
        reasons = [item["reason"] for item in body.get("error", {}).get("errors", [])
                   if isinstance(item.get("reason"), str) and re.fullmatch(r"[A-Za-z0-9_]+", item["reason"])]
    except (ValueError, TypeError, AttributeError, KeyError):
        pass
    return {"type": type(error).__name__, "http_status": status, "reasons": reasons}


def execute(request, sleep=time.sleep):
    for attempt in range(5):
        try:
            return request.execute(num_retries=0)
        except Exception as error:
            details = error_details(error)
            status = details["http_status"]
            retry = (status == 429 or (status is not None and 500 <= status < 600)
                     or (status == 403 and bool(set(details["reasons"]) & {"rateLimitExceeded", "userRateLimitExceeded"})))
            if not retry or attempt == 4:
                raise
            sleep(2 ** attempt + random.random())


def csv_row(item):
    media = item.get("videoMediaMetadata") or {}
    row = {key: item.get(key, "") for key in CSV_FIELDS}
    row.update(parent_ids=";".join(item.get("parents", [])), size_bytes=item.get("size", ""),
               duration_ms=media.get("durationMillis", ""), width=media.get("width", ""),
               height=media.get("height", ""))
    # Excel must display untrusted names as text, never formulas. JSONL stays raw.
    return {key: "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@"))
            else value for key, value in row.items()}


def inventory(root, output, service_factory, *, sleep=time.sleep):
    """Stream unique raw records to a new directory and preserve partial results."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    summary = dict(schema_version="drive-inventory/1", root_folder_id=root,
                   started_at=datetime.now(timezone.utc).isoformat(), complete=False,
                   pages=0, folders_discovered=1, folders_completed=0, files=0, videos=0,
                   shortcuts=0, duplicate_ids=0, errors=[], scope=SCOPE,
                   evidence_type="metadata_inventory_only", shortcut_policy="record_do_not_follow",
                   model_inference=False, gpu_seconds=0)
    phase = "output"
    try:
        with (output / "inventory.jsonl").open("x", encoding="utf-8") as raw, \
                (output / "videos.csv").open("x", encoding="utf-8-sig", newline="") as table:
            writer = csv.DictWriter(table, fieldnames=CSV_FIELDS)
            writer.writeheader()
            table.flush()
            phase = "authentication"
            service = service_factory()
            phase = "root_metadata"
            root_item = execute(service.files().get(fileId=root, fields=FIELDS, supportsAllDrives=True), sleep)
            if root_item.get("mimeType") != FOLDER:
                raise ValueError("Root must be a Drive folder")
            phase = "output"
            raw.write(json.dumps(root_item, ensure_ascii=False, allow_nan=False) + "\n")
            raw.flush()
            pending = deque([root])
            seen = {root}
            corpus = {"corpora": "user"}
            if root_item.get("driveId"):
                corpus = {"corpora": "drive", "driveId": root_item["driveId"]}
            while pending:
                current = pending.popleft()
                token, tokens, folder_complete = None, set(), True
                while True:
                    phase = "folder_listing"
                    try:
                        page = execute(service.files().list(
                            q=f"'{current}' in parents and trashed = false", pageSize=1000,
                            pageToken=token, fields=f"nextPageToken,incompleteSearch,files({FIELDS})",
                            supportsAllDrives=True, includeItemsFromAllDrives=True, **corpus), sleep)
                    except Exception as error:
                        summary["errors"].append(dict(folder_id=current, phase=phase, **error_details(error)))
                        folder_complete = False
                        break
                    summary["pages"] += 1
                    if page.get("incompleteSearch"):
                        folder_complete = False
                        summary["errors"].append(dict(folder_id=current, type="incompleteSearch"))
                    for item in page.get("files", []):
                        identity = item["id"]
                        if identity in seen:
                            summary["duplicate_ids"] += 1
                            continue
                        seen.add(identity)
                        phase = "output"
                        raw.write(json.dumps(item, ensure_ascii=False, allow_nan=False) + "\n")
                        raw.flush()
                        mime = item.get("mimeType", "")
                        if mime == FOLDER:
                            summary["folders_discovered"] += 1
                            pending.append(identity)
                        else:
                            summary["files"] += 1
                            if mime == SHORTCUT:
                                summary["shortcuts"] += 1
                            elif mime.startswith("video/"):
                                summary["videos"] += 1
                                writer.writerow(csv_row(item))
                                table.flush()
                    token = page.get("nextPageToken")
                    if not token:
                        break
                    if token in tokens:
                        folder_complete = False
                        summary["errors"].append(dict(folder_id=current, type="repeatedPageToken"))
                        break
                    tokens.add(token)
                summary["folders_completed"] += int(folder_complete)
                print(f"Folders {summary['folders_completed']}/{summary['folders_discovered']}; "
                      f"pages {summary['pages']}; videos {summary['videos']}", file=sys.stderr)
            summary["complete"] = not summary["errors"]
    except (Exception, KeyboardInterrupt) as error:
        summary["errors"].append(dict(phase=phase, **error_details(error)))
    finally:
        summary["finished_at"] = datetime.now(timezone.utc).isoformat()
        with (output / "summary.json").open("x", encoding="utf-8") as stream:
            json.dump(summary, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=folder_id, default=DEFAULT_FOLDER)
    parser.add_argument("--credentials", type=Path, default=auth_directory() / "credentials.json")
    parser.add_argument("--token", type=Path, default=auth_directory() / "token.json")
    parser.add_argument("--output", type=Path, required=True, help="New directory, e.g. runs/drive-inventory-01")
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("Output already exists; choose a new directory")
    if args.credentials.resolve() == args.token.resolve():
        parser.error("Credentials and token must use separate files")
    if not args.credentials.is_file() and not args.token.is_file():
        parser.error("OAuth credentials missing. Follow docs/drive-inventory.md to create a Desktop client")
    try:
        result = inventory(args.folder, args.output, lambda: create_service(args.credentials, args.token))
    except OSError:
        print("Cannot create/write output directory. Choose a new writable path.", file=sys.stderr)
        return 2
    print(json.dumps({"complete": result["complete"], "videos": result["videos"],
                      "errors": len(result["errors"]), "output": str(args.output)}))
    if not result["complete"]:
        print("Inventory incomplete; see summary.json. Authentication setup: docs/drive-inventory.md", file=sys.stderr)
        if any(error["type"] == "ModuleNotFoundError" for error in result["errors"]):
            print('Install optional dependencies with this Python: -m pip install ".[drive]"', file=sys.stderr)
        if any(error.get("phase") == "output" and error["type"] != "KeyboardInterrupt" for error in result["errors"]):
            return 2
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
