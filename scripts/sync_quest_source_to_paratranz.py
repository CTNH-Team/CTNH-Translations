"""Push the pack's quest Chinese source into the Paratranz CTNH projects.

The pack repository keeps quest text inline Chinese for in-game authoring. The
pack's own localization generator (`.github/localization/ftbquest_localization.py`)
turns that into a canonical `zh_cn.json` of `ctnh.*` keys. This script uploads
that mapping to the `CTNH/<locale>.json` file of every configured Paratranz
project, updating files in place with incremental insert/update/remove
semantics so existing translations are preserved.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from project_config import DEFAULT_CONFIG_PATH, get_project_entries, load_project_config
from sync_paratranz_to_mc import ParatranzClient

QUEST_PATH_PREFIX = "CTNH"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update the CTNH quest source file in Paratranz projects.",
    )
    parser.add_argument(
        "--zh-json",
        required=True,
        help="Path to the generated zh_cn.json quest source mapping.",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"YAML config path. Defaults to {DEFAULT_CONFIG_PATH}.",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("PARATRANZ_TOKEN"),
        help="Paratranz API token. Defaults to PARATRANZ_TOKEN.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report planned uploads without calling the API.",
    )
    return parser.parse_args()


def find_quest_file(files: list[dict[str, Any]], locale: str) -> dict[str, Any] | None:
    expected = f"{QUEST_PATH_PREFIX}/{locale}.json"
    for file_info in files:
        if file_info.get("name") == expected:
            return file_info
    return None


def summarize_result(payload: Any) -> str:
    if isinstance(payload, dict):
        if payload.get("status") == "hashMatched":
            return "unchanged (hash matched)"
        file_info = payload.get("file")
        if isinstance(file_info, dict):
            revision = payload.get("revision")
            if isinstance(revision, dict):
                return (
                    f"updated +{revision.get('insert', 0)}"
                    f"/~{revision.get('update', 0)}"
                    f"/-{revision.get('remove', 0)}"
                    f" ({file_info.get('total')} entries)"
                )
            return f"created ({file_info.get('total')} entries)"
    return str(payload)[:120]


def sync_quest_source(
    client: Any,
    project_entries: list[dict[str, Any]],
    zh_mapping: dict[str, str],
    dry_run: bool = False,
) -> list[str]:
    content = json.dumps(zh_mapping, ensure_ascii=False, indent=4).encode("utf-8")
    reports: list[str] = []
    for entry in project_entries:
        locale = str(entry["locale"])
        project_id = int(entry["project_id"])
        filename = f"{locale}.json"
        existing = find_quest_file(client.get_files(project_id), locale)
        if dry_run:
            action = "update" if existing else "create"
            reports.append(
                f"[dry-run] project {project_id}: would {action} "
                f"{QUEST_PATH_PREFIX}/{filename} ({len(zh_mapping)} entries)"
            )
            continue
        if existing:
            payload = client.upload_file(
                project_id, filename, content, QUEST_PATH_PREFIX, file_id=int(existing["id"])
            )
        else:
            payload = client.upload_file(project_id, filename, content, QUEST_PATH_PREFIX)
        reports.append(f"project {project_id} {QUEST_PATH_PREFIX}/{filename}: {summarize_result(payload)}")
    return reports


def main() -> int:
    args = parse_args()

    if not args.token:
        print("Missing Paratranz token. Pass --token or set PARATRANZ_TOKEN.", file=sys.stderr)
        return 1

    try:
        zh_path = Path(args.zh_json)
        zh_mapping = json.loads(zh_path.read_text(encoding="utf-8"))
        if not isinstance(zh_mapping, dict):
            raise ValueError(f"Not a flat JSON mapping: {zh_path}")

        config = load_project_config(args.config)
        project_entries = get_project_entries(config)
        client = ParatranzClient(token=args.token)
        reports = sync_quest_source(client, project_entries, zh_mapping, dry_run=args.dry_run)
    except Exception as error:
        print(f"Quest source sync failed: {error}", file=sys.stderr)
        return 1

    for report in reports:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
