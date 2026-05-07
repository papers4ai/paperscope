#!/usr/bin/env python3
"""
fetch_ccf_deadlines.py — Parse CCF-Deadlines YAML data into frontend/data/deadlines.json

Source: https://github.com/ccfddl/ccf-deadlines (MIT License)
Usage:  python scripts/fetch_ccf_deadlines.py /path/to/cloned/ccf-deadlines
"""

import json
import sys
import yaml
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT = ROOT / "frontend" / "data" / "deadlines.json"

# Only include these CCF ranks; set to None to include all
INCLUDE_RANKS = {"A", "B"}

# Subcategories to include (match ccfddl's "sub" field)
INCLUDE_SUBS = {"AI", "CV", "CG", "HCI", "DM", "DB", "IR", "NLP", "SC", "SE", "HPC", "MX"}

# Keep conferences with deadline within this many days in the past (grace window)
PAST_GRACE_DAYS = 30
# Keep conferences with deadline this many days in the future
FUTURE_WINDOW_DAYS = 365


def parse_deadline(dt_str: str | None, tz_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            # Apply timezone offset
            offset_hours = 0
            if tz_str:
                tz_str = str(tz_str).strip()
                if tz_str.startswith("UTC") or tz_str.startswith("GMT"):
                    sign_str = tz_str[3:].strip()
                    if sign_str:
                        try:
                            offset_hours = float(sign_str)
                        except ValueError:
                            pass
            dt = dt.replace(tzinfo=timezone(timedelta(hours=offset_hours)))
        return dt
    except Exception:
        return None


def main(repo_path: str):
    repo = Path(repo_path)
    conf_dir = repo / "conference"
    if not conf_dir.exists():
        print(f"Conference directory not found: {conf_dir}", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(timezone.utc)
    cutoff_past = now - timedelta(days=PAST_GRACE_DAYS)
    cutoff_future = now + timedelta(days=FUTURE_WINDOW_DAYS)

    entries = []

    for yaml_file in sorted(conf_dir.rglob("*.yml")):
        try:
            with open(yaml_file, encoding="utf-8") as f:
                docs = yaml.safe_load(f)
        except Exception as e:
            print(f"  warn: {yaml_file.name}: {e}", file=sys.stderr)
            continue

        if not isinstance(docs, list):
            docs = [docs]

        for doc in docs:
            if not isinstance(doc, dict):
                continue

            title = doc.get("title", "")
            full_name = doc.get("description", title)
            sub = doc.get("sub", "")
            rank_info = doc.get("rank", {}) or {}
            ccf = str(rank_info.get("ccf", "")).upper().strip()
            core = str(rank_info.get("core", "")).strip()

            if INCLUDE_RANKS and ccf not in INCLUDE_RANKS:
                continue
            if sub not in INCLUDE_SUBS:
                continue

            confs = doc.get("confs", []) or []
            for conf in confs:
                if not isinstance(conf, conf_type := dict):
                    continue
                year = conf.get("year")
                conf_id = conf.get("id", f"{title}{year}")
                link = conf.get("link", "")
                date_str = conf.get("date", "")
                place = conf.get("place", "")
                timezone_str = conf.get("timezone", "UTC-12")

                timeline = conf.get("timeline", []) or []
                if not timeline:
                    continue

                # Use first (main) timeline entry
                tl = timeline[0] if isinstance(timeline[0], dict) else {}
                deadline_dt = parse_deadline(tl.get("deadline"), timezone_str)
                abstract_dt = parse_deadline(tl.get("abstract_deadline"), timezone_str)
                comment = tl.get("comment", "")

                if deadline_dt is None:
                    continue
                if deadline_dt < cutoff_past or deadline_dt > cutoff_future:
                    continue

                entries.append({
                    "id": conf_id,
                    "title": title,
                    "full_name": full_name,
                    "sub": sub,
                    "ccf": ccf,
                    "core": core,
                    "year": year,
                    "deadline": deadline_dt.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "abstract_deadline": abstract_dt.strftime("%Y-%m-%dT%H:%M:%S%z") if abstract_dt else None,
                    "timezone": timezone_str,
                    "date": date_str,
                    "place": place,
                    "link": link,
                    "comment": comment,
                })

    # Sort by deadline ascending
    entries.sort(key=lambda x: x["deadline"])

    result = {
        "generated": date.today().isoformat(),
        "total": len(entries),
        "conferences": entries,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(entries)} conferences → {OUTPUT}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_ccf_deadlines.py <ccf-deadlines-repo-path>")
        sys.exit(1)
    main(sys.argv[1])
