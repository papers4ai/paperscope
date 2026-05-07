#!/usr/bin/env python3
"""
fetch_ccf_deadlines.py — Sync CCF-Deadlines data into frontend/data/deadlines.json

Two modes:
  --online   Fetch directly from ccfddl's deployed allconf.yml (default, no repo needed)
  <repo>     Parse from a locally cloned ccfddl repo

Source: https://github.com/ccfddl/ccf-deadlines (MIT License)
"""

import json
import sys
import urllib.request
import yaml
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT = ROOT / "frontend" / "data" / "deadlines.json"

ALLCONF_URL = "https://ccfddl.github.io/conference/allconf.yml"
PAST_GRACE_DAYS = 180
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
                s = str(tz_str).strip().upper()
                if s.startswith(("UTC", "GMT")):
                    sign = s[3:].strip()
                    if sign:
                        try:
                            offset_hours = float(sign)
                        except ValueError:
                            pass
            dt = dt.replace(tzinfo=timezone(timedelta(hours=offset_hours)))
        return dt
    except Exception:
        return None


def load_docs_from_url(url):
    print(f"Fetching {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "paperscope/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        content = r.read().decode("utf-8")
    docs = list(yaml.safe_load_all(content))
    # allconf.yml is a single YAML list of dicts
    if len(docs) == 1 and isinstance(docs[0], list):
        return docs[0]
    return [d for d in docs if isinstance(d, dict)]


def load_docs_from_repo(repo_path):
    repo = Path(repo_path)
    conf_dir = repo / "conference"
    if not conf_dir.exists():
        print(f"Conference directory not found: {conf_dir}", file=sys.stderr)
        sys.exit(1)
    docs = []
    for yml in sorted(conf_dir.rglob("*.yml")):
        if yml.name == "types.yml":
            continue
        try:
            with open(yml, encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
            if isinstance(loaded, list):
                docs.extend(loaded)
            elif isinstance(loaded, dict):
                docs.append(loaded)
        except Exception as e:
            print(f"  warn: {yml.name}: {e}", file=sys.stderr)
    return docs


def process_docs(docs):
    now = datetime.now(timezone.utc)
    cutoff_past = now - timedelta(days=PAST_GRACE_DAYS)
    cutoff_future = now + timedelta(days=FUTURE_WINDOW_DAYS)
    entries = []

    for doc in docs:
        if not isinstance(doc, dict):
            continue
        title = doc.get("title", "")
        full_name = doc.get("description", title)
        sub = doc.get("sub", "")
        rank_info = doc.get("rank") or {}
        ccf = str(rank_info.get("ccf", "")).upper().strip()
        # keep all conferences — frontend CCF A/B/C buttons handle filtering

        for conf in (doc.get("confs") or []):
            if not isinstance(conf, dict):
                continue
            timeline = conf.get("timeline") or []
            tz_str = conf.get("timezone", "UTC-12")
            seen_ids = set()

            for tl in timeline:
                if not isinstance(tl, dict):
                    continue
                deadline_dt = parse_deadline(tl.get("deadline"), tz_str)
                if deadline_dt is None:
                    continue
                if deadline_dt < cutoff_past or deadline_dt > cutoff_future:
                    continue

                abstract_dt = parse_deadline(tl.get("abstract_deadline"), tz_str)
                entry_id = conf.get("id", f"{title}{conf.get('year','')}")
                # deduplicate if multiple rounds share the same conf id
                uniq_key = f"{entry_id}_{deadline_dt.strftime('%Y%m%d')}"
                if uniq_key in seen_ids:
                    continue
                seen_ids.add(uniq_key)

                entries.append({
                    "id": uniq_key,
                    "title": title,
                    "full_name": full_name,
                    "sub": sub,
                    "sub_name": SUB_NAMES.get(sub, sub),
                    "ccf": ccf,
                    "core": str(rank_info.get("core", "") or ""),
                    "year": conf.get("year"),
                    "deadline": deadline_dt.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "abstract_deadline": abstract_dt.strftime("%Y-%m-%dT%H:%M:%S%z") if abstract_dt else None,
                    "timezone": tz_str,
                    "date": conf.get("date", ""),
                    "place": conf.get("place", ""),
                    "link": conf.get("link", ""),
                    "comment": tl.get("comment", ""),
                })

    entries.sort(key=lambda x: x["deadline"])
    return entries


def main():
    use_online = "--online" in sys.argv or (len(sys.argv) == 1)
    repo_path = None
    for arg in sys.argv[1:]:
        if arg != "--online":
            repo_path = arg

    if use_online or repo_path is None:
        docs = load_docs_from_url(ALLCONF_URL)
    else:
        docs = load_docs_from_repo(repo_path)

    entries = process_docs(docs)

    result = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": ALLCONF_URL if (use_online or repo_path is None) else str(repo_path),
        "total": len(entries),
        "conferences": entries,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(entries)} conferences → {OUTPUT}")
    print(f"Generated: {result['generated']}")


if __name__ == "__main__":
    main()
