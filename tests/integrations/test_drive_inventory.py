import argparse
import csv
import json
from types import SimpleNamespace

import pytest

from eventcaption_ai import drive_inventory as drive


class ApiError(Exception):
    def __init__(self, status, reason="forbidden"):
        super().__init__("SECRET: must never appear in logs")
        self.resp = SimpleNamespace(status=status)
        self.content = json.dumps({"error": {"errors": [{"reason": reason}]}}).encode()


class Request:
    def __init__(self, responses):
        self.responses = list(responses)

    def execute(self, num_retries):
        assert num_retries == 0
        result = self.responses.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class FakeDrive:
    def __init__(self, pages, root=None):
        self.pages = pages
        self.root = root or {"id": "root", "name": "Videos", "mimeType": drive.FOLDER}
        self.calls = []

    def files(self):
        return self

    def get(self, **kwargs):
        assert kwargs["fileId"] == "root"
        assert kwargs["supportsAllDrives"] is True
        assert "alt" not in kwargs
        return Request([self.root])

    def list(self, **kwargs):
        self.calls.append(kwargs)
        assert kwargs["pageSize"] == 1000
        assert kwargs["q"].endswith("in parents and trashed = false")
        key = (kwargs["q"].split("'")[1], kwargs["pageToken"])
        response = self.pages[key]
        return Request(response if isinstance(response, list) else [response])


def video(number, **extra):
    return dict(id=f"v{number}", name=f"video{number}.mp4", mimeType="video/mp4", **extra)


def test_over_2000_files_empty_page_recursion_dedup_and_raw_metadata(tmp_path):
    child = {"id": "child", "name": "Nested", "mimeType": drive.FOLDER}
    shortcut = {"id": "link", "mimeType": drive.SHORTCUT,
                "shortcutDetails": {"targetId": "outside", "targetMimeType": drive.FOLDER}}
    first = video(0, videoMediaMetadata={"durationMillis": "31000", "width": 256, "height": 144},
                  parents=["root"], sha256Checksum="abc", size="1200")
    pages = {
        ("root", None): {"files": [first] + [video(i) for i in range(1, 1000)], "nextPageToken": "a"},
        ("root", "a"): {"files": [], "nextPageToken": "b"},
        ("root", "b"): {"files": [video(i) for i in range(1000, 2000)], "nextPageToken": "c"},
        ("root", "c"): {"files": [child, shortcut, first, video(2000)]},
        ("child", None): {"files": [video(2001, parents=["child"]), child,
                                    dict(video(2002), name="video0.mp4"),
                                    dict(video(2003), name="=FORMULA.mp4")]},
    }
    service = FakeDrive(pages)
    summary = drive.inventory("root", tmp_path / "out", lambda: service)
    assert summary["complete"] is True
    assert summary["pages"] == 5
    assert summary["videos"] == 2004
    assert summary["folders_completed"] == summary["folders_discovered"] == 2
    assert summary["duplicate_ids"] == 2
    assert summary["shortcuts"] == 1
    raw = [json.loads(line) for line in (tmp_path / "out/inventory.jsonl").read_text(encoding="utf-8").splitlines()]
    assert first in raw
    assert raw[-1]["name"] == "=FORMULA.mp4"
    assert len({row["id"] for row in raw}) == len(raw)
    assert (tmp_path / "out/videos.csv").read_bytes().startswith(b"\xef\xbb\xbf")
    with (tmp_path / "out/videos.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["duration_ms"] == "31000"
    assert rows[1]["duration_ms"] == rows[1]["webViewLink"] == ""
    assert rows[-1]["name"] == "'=FORMULA.mp4"
    assert rows[-2]["name"] == rows[0]["name"]  # Same name, different ID survives.


@pytest.mark.parametrize("status,reason", [(429, "rateLimitExceeded"), (503, "backendError"),
                                          (403, "userRateLimitExceeded")])
def test_retry_transient_only(status, reason):
    waits = []
    assert drive.execute(Request([ApiError(status, reason), {"files": []}]), waits.append) == {"files": []}
    assert len(waits) == 1 and 1 <= waits[0] < 2
    waits.clear()
    with pytest.raises(ApiError):
        drive.execute(Request([ApiError(status, reason)] * 5), waits.append)
    assert len(waits) == 4
    assert all(delay < 10 for delay in waits)


def test_failure_preserves_records_and_continues_other_folders(tmp_path, capsys):
    pages = {("root", None): {"files": [video(0), {"id": "child", "mimeType": drive.FOLDER}], "nextPageToken": "p"},
             ("root", "p"): ApiError(403), ("child", None): {"files": [video(1)]}}
    waits = []
    summary = drive.inventory("root", tmp_path / "out", lambda: FakeDrive(pages), sleep=waits.append)
    assert not summary["complete"]
    assert summary["videos"] == 2
    assert summary["folders_completed"] == 1
    assert summary["errors"][0]["http_status"] == 403
    assert waits == []
    assert "SECRET" not in json.dumps(summary) + capsys.readouterr().err
    assert len((tmp_path / "out/inventory.jsonl").read_text().splitlines()) == 4


@pytest.mark.parametrize("page,error", [({"files": [video(0)], "incompleteSearch": True}, "incompleteSearch"),
                                      ({"files": [], "nextPageToken": "again"}, "repeatedPageToken")])
def test_incomplete_search_and_token_cycle(tmp_path, page, error):
    service = FakeDrive({("root", None): page, ("root", "again"): page})
    summary = drive.inventory("root", tmp_path / "out", lambda: service)
    assert not summary["complete"]
    assert summary["errors"][-1]["type"] == error


def test_shared_drive_uses_narrow_corpus_and_root_must_be_folder(tmp_path):
    service = FakeDrive({("root", None): {}}, {"id": "root", "mimeType": drive.FOLDER, "driveId": "shared"})
    assert drive.inventory("root", tmp_path / "shared", lambda: service)["complete"]
    assert service.calls[0]["corpora"] == "drive"
    assert service.calls[0]["driveId"] == "shared"
    summary = drive.inventory("root", tmp_path / "wrong", lambda: FakeDrive({}, video(1)))
    assert not summary["complete"] and summary["errors"][0]["type"] == "ValueError"


def test_interrupt_and_factory_error_leave_incomplete_summary(tmp_path):
    def interrupted():
        raise KeyboardInterrupt()
    summary = drive.inventory("root", tmp_path / "interrupted", interrupted)
    assert not summary["complete"]
    assert summary["errors"][0]["type"] == "KeyboardInterrupt"
    assert json.loads((tmp_path / "interrupted/summary.json").read_text())["complete"] is False
    with pytest.raises(FileExistsError):
        drive.inventory("root", tmp_path / "interrupted", lambda: pytest.fail("No overwrite"))


def test_folder_parser_and_external_auth_location(monkeypatch, tmp_path):
    assert drive.folder_id(" https://drive.google.com/drive/folders/abc-123?usp=sharing ") == "abc-123"
    assert drive.folder_id("https://drive.google.com/drive/u/0/folders/abc/") == "abc"
    for bad in ["", "x' or true", "https://evil.test/drive/folders/abc", "https://drive.google.com/file/d/abc"]:
        with pytest.raises(argparse.ArgumentTypeError):
            drive.folder_id(bad)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert drive.auth_directory() == tmp_path / "EventCaption-AI/google-drive"
    monkeypatch.delenv("LOCALAPPDATA")
    assert drive.auth_directory().is_absolute()


def test_cli_preflight_exit_codes_and_never_overwrites(tmp_path, monkeypatch):
    credentials = tmp_path / "credentials.json"
    credentials.write_text("{}")
    out = tmp_path / "out"
    args = ["--folder", "root", "--credentials", str(credentials), "--token", str(tmp_path / "token.json"),
            "--output", str(out)]
    monkeypatch.setattr(drive, "create_service", lambda *args: FakeDrive({("root", None): {"files": []}}))
    assert drive.main(args) == 0
    before = (out / "summary.json").read_bytes()
    with pytest.raises(SystemExit) as error:
        drive.main(args)
    assert error.value.code == 2
    assert (out / "summary.json").read_bytes() == before
    monkeypatch.setattr(drive, "create_service", lambda *args: FakeDrive({("root", None): ApiError(404)}))
    assert drive.main(args[:-1] + [str(tmp_path / "failed")]) == 1
    with pytest.raises(SystemExit):
        drive.main(["--credentials", str(tmp_path / "absent"), "--token", str(tmp_path / "absent-token"),
                    "--output", str(tmp_path / "missing")])
    with pytest.raises(SystemExit):
        drive.main(["--credentials", str(credentials), "--token", str(credentials), "--output", str(tmp_path / "same")])


def test_oauth_scope_cache_refresh_and_new_login_without_network(tmp_path, monkeypatch):
    import sys
    from types import ModuleType

    calls = []
    class Credential:
        valid = False
        expired = True
        refresh_token = "fake"
        granted_scopes = [drive.SCOPE]
        scopes = [drive.SCOPE]

        def refresh(self, request):
            calls.append("refresh")

        def to_json(self):
            return json.dumps({"scopes": self.scopes})

    credential = Credential()
    class Credentials:
        @staticmethod
        def from_authorized_user_info(info, scopes):
            assert scopes == [drive.SCOPE]
            return credential

    class Flow:
        @staticmethod
        def from_client_secrets_file(path, scopes):
            assert scopes == [drive.SCOPE]
            calls.append("flow")
            return Flow()

        def run_local_server(self, **kwargs):
            assert kwargs == dict(host="localhost", port=0, timeout_seconds=300)
            return credential

    fake_modules = {
        "google.auth.transport.requests": {"Request": lambda: object()},
        "google.oauth2.credentials": {"Credentials": Credentials},
        "google_auth_oauthlib.flow": {"InstalledAppFlow": Flow},
        "googleapiclient.discovery": {"build": lambda *a, **kw: "service"},
        "google_auth_httplib2": {"AuthorizedHttp": lambda *a, **kw: object()},
        "httplib2": {"Http": lambda **kw: object()},
    }
    for name, attributes in fake_modules.items():
        module = ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
    client, token = tmp_path / "client.json", tmp_path / "private/token.json"
    assert drive.create_service(client, token) == "service"
    assert calls == ["flow"]
    assert drive.create_service(client, token) == "service"
    assert calls[-1] == "refresh"
    credential.valid = True
    assert drive.create_service(client, token) == "service"
    token.write_text(json.dumps({"scopes": [drive.SCOPE, "https://www.googleapis.com/auth/drive"]}))
    with pytest.raises(ValueError):
        drive.create_service(client, token)
    new_token = tmp_path / "other.json"
    credential.granted_scopes = ["https://www.googleapis.com/auth/drive"]
    with pytest.raises(ValueError):
        drive.create_service(client, new_token)
    assert not new_token.exists()
