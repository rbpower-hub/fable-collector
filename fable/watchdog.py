"""Run outside GitHub Actions to recover missed scheduled collections."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import urllib.request
from typing import Any

from .healthcheck import DEFAULT_BASE, check_live


def github_request(repo: str, token: str, endpoint: str, payload: dict | None = None) -> Any:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/workflows/collect.yml/{endpoint}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "Fable-watchdog",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read()
        return json.loads(body) if body else None


def recovery_pending(runs: list[dict], now: dt.datetime) -> bool:
    for run in runs:
        if run.get("status") in {"queued", "in_progress", "waiting", "pending", "requested"}:
            return True
        if run.get("event") == "workflow_dispatch":
            created = dt.datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
            if (now - created).total_seconds() < 600:
                return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dispatch", action="store_true", help="Enable recovery; otherwise check only")
    args = parser.parse_args()
    problems = check_live(os.getenv("FABLE_BASE_URL", DEFAULT_BASE))
    if not problems:
        print("Production fresh and complete")
        return 0
    print("\n".join(problems))
    if not args.dispatch:
        return 1
    token = os.getenv("FABLE_GITHUB_TOKEN")
    if not token:
        print("FABLE_GITHUB_TOKEN is required to dispatch recovery")
        return 2
    repo = os.getenv("FABLE_GITHUB_REPOSITORY", "rbpower-hub/fable-collector")
    try:
        runs = github_request(repo, token, "runs?per_page=30")
        if recovery_pending(runs["workflow_runs"], dt.datetime.now(dt.timezone.utc)):
            print("Collection queued, running, or recently dispatched; waiting for the next check")
            return 0
        github_request(repo, token, "dispatches", {"ref": "main"})
    except Exception as error:  # noqa: BLE001
        print(f"Recovery dispatch failed: {type(error).__name__}")
        return 2
    print("Recovery requested; deployment must be confirmed by the next check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
