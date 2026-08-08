#!/usr/bin/env python3
"""GitHub Issues -> queue worker for the free GitHub deployment flow.

The workflow keeps the repo public and serializes jobs through GitHub Actions.
Users submit a queue issue with a video attachment or a public source URL.
This worker:

1. Parses the task parameters from the issue body.
2. Downloads the source video.
3. Runs the existing depth conversion pipeline.
4. Writes the result into `queue-output/` for artifact upload.
5. Updates the issue with status comments and labels.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from depth_converter import MODEL_DEFS, normalize_resolution_choice, process_video


QUEUE_LABEL = "queue-video"
PROCESSING_LABEL = "queue-processing"
DONE_LABEL = "queue-done"
ERROR_LABEL = "queue-error"

ALLOWED_MODEL_PREFIXES = ("small", "base")
QUEUE_BLOCK_RE = re.compile(r"```queue\s*(.*?)```", re.IGNORECASE | re.DOTALL)
URL_RE = re.compile(r"https?://[^\s<>\")]+", re.IGNORECASE)
TRUE_VALUES = {"1", "true", "yes", "y", "on"}
FALSE_VALUES = {"0", "false", "no", "n", "off"}
MAX_INPUT_MB = float(os.environ.get("QUEUE_MAX_INPUT_MB", "120"))
ALLOWED_SOURCE_SUFFIXES = (
    "github.com",
    "githubusercontent.com",
    "githubassets.com",
)


def _token() -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required")
    return token


def _repo() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY is required")
    return repo


def _api_base() -> str:
    return os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")


def gh_api(method: str, path: str, payload: Any | None = None) -> Any:
    url = f"{_api_base()}{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {_token()}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "contour-control-tool-queue-worker",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {path} failed: {exc.code} {body}") from exc


def _event_payload() -> dict[str, Any]:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        return {}
    path = Path(event_path)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _issue_number_from_event(event: dict[str, Any], arg_issue_number: int | None) -> int:
    if arg_issue_number is not None:
        return arg_issue_number
    issue = event.get("issue") or {}
    number = issue.get("number")
    if isinstance(number, int):
        return number
    raise RuntimeError("Unable to determine issue number")


def _issue_from_event_or_api(event: dict[str, Any], issue_number: int) -> dict[str, Any]:
    issue = event.get("issue")
    if isinstance(issue, dict) and issue.get("number") == issue_number:
        return issue
    return gh_api("GET", f"/repos/{_repo()}/issues/{issue_number}")


def _issue_comments(issue_number: int) -> list[dict[str, Any]]:
    comments = gh_api("GET", f"/repos/{_repo()}/issues/{issue_number}/comments")
    return comments if isinstance(comments, list) else []


def _ensure_labels() -> None:
    labels = {
        QUEUE_LABEL: ("1f6feb", "Queue submission"),
        PROCESSING_LABEL: ("d29922", "Processing"),
        DONE_LABEL: ("2da44e", "Completed"),
        ERROR_LABEL: ("d1242f", "Failed"),
    }
    for name, (color, description) in labels.items():
        try:
            gh_api(
                "POST",
                f"/repos/{_repo()}/labels",
                {"name": name, "color": color, "description": description},
            )
        except RuntimeError as exc:
            if "422" not in str(exc):
                raise


def _label_names(issue: dict[str, Any]) -> set[str]:
    labels = issue.get("labels") or []
    names: set[str] = set()
    for label in labels:
        if isinstance(label, dict) and isinstance(label.get("name"), str):
            names.add(label["name"])
    return names


def _add_labels(issue_number: int, names: Iterable[str]) -> None:
    payload = [name for name in names]
    if payload:
        gh_api("POST", f"/repos/{_repo()}/issues/{issue_number}/labels", payload)


def _remove_label(issue_number: int, name: str) -> None:
    try:
        gh_api(
            "DELETE",
            f"/repos/{_repo()}/issues/{issue_number}/labels/{urllib.parse.quote(name, safe='')}",
        )
    except RuntimeError as exc:
        if "404" not in str(exc):
            raise


def _create_comment(issue_number: int, body: str) -> None:
    gh_api("POST", f"/repos/{_repo()}/issues/{issue_number}/comments", {"body": body})


def _queue_block(text: str) -> dict[str, str]:
    match = QUEUE_BLOCK_RE.search(text or "")
    if not match:
        return {}

    config: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        config[key.strip().lower().replace("-", "_")] = value.strip()
    return config


def _first_attachment_url(texts: Iterable[str]) -> str:
    for text in texts:
        for url in URL_RE.findall(text or ""):
            lowered = url.lower()
            if "user-attachments/assets" in lowered or "githubusercontent.com" in lowered:
                return url
    for text in texts:
        for url in URL_RE.findall(text or ""):
            suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
            if suffix in {".mp4", ".mov", ".m4v", ".webm", ".mkv"}:
                return url
    return ""


def _validate_source_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme != "https":
        raise RuntimeError("Only https source URLs are allowed.")
    if not parsed.hostname:
        raise RuntimeError("Source URL is missing a hostname.")

    host = parsed.hostname.lower()
    if host.endswith(ALLOWED_SOURCE_SUFFIXES):
        return url

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise RuntimeError(f"Cannot resolve source host: {host}") from exc

    seen_global = False
    for info in infos:
        ip_text = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_text)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise RuntimeError(f"Blocked non-public source host: {host}")
        if ip.is_global:
            seen_global = True

    if not seen_global:
        raise RuntimeError(f"Blocked non-public source host: {host}")

    return url


def _coerce_bool(value: str, default: bool = False) -> bool:
    lowered = value.strip().lower()
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    return default


def _coerce_float(value: str, default: float = 60.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _allowed_model(model: str) -> str:
    model = model.strip()
    if model in MODEL_DEFS:
        return model

    lowered = model.lower()
    for key in MODEL_DEFS:
        if key.lower() == lowered:
            return key

    if lowered.startswith("small"):
        return next(key for key in MODEL_DEFS if key.lower().startswith("small"))
    if lowered.startswith("base"):
        return next(key for key in MODEL_DEFS if key.lower().startswith("base"))
    if lowered.startswith("large"):
        raise RuntimeError("Large is disabled for the free GitHub queue. Use Small or Base.")

    raise RuntimeError(f"Unknown model: {model}")


def _validate_model(model: str) -> str:
    normalized = _allowed_model(model)
    if not any(normalized.lower().startswith(prefix) for prefix in ALLOWED_MODEL_PREFIXES):
        raise RuntimeError("Only Small and Base are enabled in the free GitHub queue.")
    return normalized


def _find_source(issue: dict[str, Any], config: dict[str, str], comments: list[dict[str, Any]]) -> str:
    source = config.get("source", "attachment").strip()
    if source and source.lower() != "attachment":
        return source

    candidates = [issue.get("body", "")]
    candidates.extend(comment.get("body", "") for comment in comments)
    return _first_attachment_url(str(text) for text in candidates)


def _queue_position(issue_number: int) -> int:
    issues = gh_api(
        "GET",
        f"/repos/{_repo()}/issues?state=open&labels={urllib.parse.quote(QUEUE_LABEL)}&per_page=100&sort=created&direction=asc",
    )
    if not isinstance(issues, list):
        return 1
    earlier = 0
    for item in issues:
        if isinstance(item, dict) and isinstance(item.get("number"), int) and item["number"] < issue_number:
            earlier += 1
    return earlier + 1


def _download(url: str, dest: Path) -> tuple[Path, int]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "contour-control-tool-queue-worker"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        total_size = int(response.headers.get("Content-Length") or 0)
        if total_size and total_size > MAX_INPUT_MB * 1024 * 1024:
            raise RuntimeError(
                f"Input file is too large for the free queue: {total_size / 1024 / 1024:.1f} MB "
                f"(limit {MAX_INPUT_MB:.0f} MB)."
            )

        disposition = response.headers.get("Content-Disposition", "")
        filename = ""
        match = re.search(r'filename="?([^";]+)"?', disposition, re.IGNORECASE)
        if match:
            filename = match.group(1)
        if not filename:
            filename = Path(urllib.parse.urlparse(url).path).name or "input.mp4"

        suffix = Path(filename).suffix or ".mp4"
        target = dest.with_suffix(suffix)
        bytes_written = 0
        with open(target, "wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                bytes_written += len(chunk)
                if bytes_written > MAX_INPUT_MB * 1024 * 1024:
                    handle.close()
                    target.unlink(missing_ok=True)
                    raise RuntimeError(
                        f"Input file is too large for the free queue: {bytes_written / 1024 / 1024:.1f} MB "
                        f"(limit {MAX_INPUT_MB:.0f} MB)."
                    )
        return target, bytes_written


def _progress_logger(issue_number: int):
    def _log(fraction: float, description: str) -> None:
        pct = int(max(0.0, min(fraction, 1.0)) * 100)
        print(f"[issue #{issue_number}] {pct:3d}% {description}")

    return _log


def _output_dir(issue_number: int) -> Path:
    root = ROOT / "queue-output" / f"issue-{issue_number}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_summary(output_dir: Path, summary: dict[str, Any]) -> None:
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Process one GitHub issue queue job.")
    parser.add_argument("--issue-number", type=int, default=None)
    parser.add_argument("--event-path", default=os.environ.get("GITHUB_EVENT_PATH"))
    args = parser.parse_args()

    event = {}
    if args.event_path:
        path = Path(args.event_path)
        if path.is_file():
            event = json.loads(path.read_text(encoding="utf-8"))

    issue_number = _issue_number_from_event(event, args.issue_number)
    issue = _issue_from_event_or_api(event, issue_number)
    comments = _issue_comments(issue_number)

    _ensure_labels()

    labels = _label_names(issue)
    if DONE_LABEL in labels:
        _remove_label(issue_number, QUEUE_LABEL)
        print(f"Issue #{issue_number} is already done; skipping.")
        return 0

    looks_like_queue_job = "```queue" in (issue.get("body") or "") or "[queue]" in (issue.get("title") or "").lower()
    if QUEUE_LABEL not in labels and not looks_like_queue_job:
        print(f"Issue #{issue_number} does not have the queue label; skipping.")
        return 0
    if QUEUE_LABEL not in labels:
        _add_labels(issue_number, [QUEUE_LABEL])
    _remove_label(issue_number, ERROR_LABEL)

    config = _queue_block(issue.get("body", ""))
    model = _validate_model(config.get("model", next(k for k in MODEL_DEFS if k.lower().startswith("small"))))
    resolution = normalize_resolution_choice(config.get("resolution", "Original"))
    invert_bw = _coerce_bool(config.get("invert", "false"))
    smoothing = max(0.0, min(100.0, _coerce_float(config.get("smoothing", "60"))))
    preserve_audio = _coerce_bool(config.get("preserve_audio", "true"), default=True)

    source_url = _find_source(issue, config, comments)
    if not source_url:
        _add_labels(issue_number, [ERROR_LABEL])
        _remove_label(issue_number, PROCESSING_LABEL)
        _remove_label(issue_number, QUEUE_LABEL)
        _create_comment(
            issue_number,
            "Queue worker could not find a source video.\n\n"
            "Attach one MP4 or MOV to the issue body, or set `source=` to a direct public URL in the ```queue``` block.",
        )
        raise RuntimeError("No source video found in issue body or comments")
    source_url = _validate_source_url(source_url)

    queue_position = _queue_position(issue_number)
    run_url = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{_repo()}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"

    _add_labels(issue_number, [PROCESSING_LABEL])
    _create_comment(
        issue_number,
        "\n".join(
            [
                "Queue job accepted.",
                "",
                f"- Position: approx. #{queue_position}",
                f"- Model: `{model}`",
                f"- Resolution: `{resolution}`",
                f"- Invert: `{invert_bw}`",
                f"- Smoothing: `{smoothing:.0f}`",
                f"- Audio: `{preserve_audio}`",
                f"- Run: {run_url}",
                "",
                "The output will appear as a workflow artifact when this run finishes.",
            ]
        ),
    )

    output_dir = _output_dir(issue_number)
    work_dir = Path(tempfile.mkdtemp(prefix=f"queue-{issue_number}-", dir=str(output_dir)))
    try:
        source_path, bytes_written = _download(source_url, work_dir / "input")
        print(f"[issue #{issue_number}] downloaded {bytes_written} bytes from {source_url}")

        result_path = process_video(
            input_video_path=str(source_path),
            model_size_label=model,
            resolution_choice=resolution,
            invert_bw=invert_bw,
            smoothing_strength=smoothing,
            preserve_audio=preserve_audio,
            progress=_progress_logger(issue_number),
        )

        final_path = output_dir / "output.mp4"
        shutil.copy2(result_path, final_path)
        _write_summary(
            output_dir,
            {
                "issue_number": issue_number,
                "title": issue.get("title", ""),
                "model": model,
                "resolution": resolution,
                "invert": invert_bw,
                "smoothing": smoothing,
                "preserve_audio": preserve_audio,
                "source_url": source_url,
                "run_url": run_url,
                "artifact_path": str(final_path.relative_to(ROOT)),
            },
        )

        _remove_label(issue_number, PROCESSING_LABEL)
        _remove_label(issue_number, QUEUE_LABEL)
        _add_labels(issue_number, [DONE_LABEL])
        _create_comment(
            issue_number,
            "\n".join(
                [
                    "Queue job finished.",
                    "",
                    f"- Output: `{final_path.relative_to(ROOT)}`",
                    f"- Artifact: `queue-output-issue-{issue_number}`",
                    f"- Run: {run_url}",
                ]
            ),
        )
        return 0
    except Exception as exc:
        _remove_label(issue_number, PROCESSING_LABEL)
        _remove_label(issue_number, QUEUE_LABEL)
        _add_labels(issue_number, [ERROR_LABEL])
        _create_comment(
            issue_number,
            "\n".join(
                [
                    "Queue job failed.",
                    "",
                    f"- Error: `{exc}`",
                    f"- Run: {run_url}",
                ]
            ),
        )
        raise
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
