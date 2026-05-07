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

INCLUDE_RANKS = {"A", "B", "C"}

PAST_GRACE_DAYS = 14
FUTURE_WINDOW_DAYS = 365

SUB_NAMES = {
    "AI": "Artificial Intelligence",
    "CG": "Graphics & Multimedia",
    "CT": "Computing Theory",
    "DB": "Database / Data Mining",
    "DS": "Computer Architecture",
    "HI": "Human-Computer Interaction",
    "MX": "Interdisciplinary",
    "NW": "Network Systems",
    "SC": "Security",
    "SE": "Software Engineering",
}


def parse_deadline(dt_str, tz_str):
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            offset_hours = 0
            if tz_str:
                tz_str = str(tz_str).strip()
                if tz_str.upper().startswith(("UTC", "GMT")):
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


def main(repo_path):
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
        if yaml_file.name == "types.yml":
            continue
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
            rank_info = doc.get("rank") or {}
            ccf = str(rank_info.get("ccf", "")).upper().strip()

            if INCLUDE_RANKS and ccf not in INCLUDE_RANKS:
                continue

            for conf in (doc.get("confs") or []):
                if not isinstance(conf, dict):
                    continue
                year = conf.get("year")
                timeline = conf.get("timeline") or []
                if not timeline:
                    continue

                tl = timeline[0] if isinstance(timeline[0], dict) else {}
                tz_str = conf.get("timezone", "UTC-12")
                deadline_dt = parse_deadline(tl.get("deadline"), tz_str)
                abstract_dt = parse_deadline(tl.get("abstract_deadline"), tz_str)

                if deadline_dt is None:
                    continue
                if deadline_dt < cutoff_past or deadline_dt > cutoff_future:
                    continue

                entries.append({
                    "id": conf.get("id", f"{title}{year}"),
                    "title": title,
                    "full_name": full_name,
                    "sub": sub,
                    "sub_name": SUB_NAMES.get(sub, sub),
                    "ccf": ccf,
                    "year": year,
                    "deadline": deadline_dt.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "abstract_deadline": abstract_dt.strftime("%Y-%m-%dT%H:%M:%S%z") if abstract_dt else None,
                    "timezone": tz_str,
                    "date": conf.get("date", ""),
                    "place": conf.get("place", ""),
                    "link": conf.get("link", ""),
                    "comment": tl.get("comment", ""),
                })

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
