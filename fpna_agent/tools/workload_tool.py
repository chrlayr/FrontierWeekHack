import json
from pathlib import Path
from collections import defaultdict


DATA_FILE = Path(__file__).parent.parent / "data" / "workload.json"


def get_workload() -> str:
    """
    Convert operational workload data into structured
    planning-relevant evidence.

    MVP source: synthetic JSON.
    Future source: Jira API.
    """

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        items = json.load(file)

    by_month = defaultdict(int)
    external_by_month = defaultdict(int)
    active_epics = set()

    total_remaining = 0
    external_remaining = 0

    for item in items:
        remaining = item["remaining_person_days"]
        month = item["target_month"]

        total_remaining += remaining
        by_month[month] += remaining
        active_epics.add(item["epic"])

        if item["work_type"] == "External Development":
            external_remaining += remaining
            external_by_month[month] += remaining

    result = {
        "source": "workload_mock",
        "total_remaining_person_days": total_remaining,
        "external_remaining_person_days": external_remaining,
        "by_month": dict(by_month),
        "external_by_month": dict(external_by_month),
        "active_epics": sorted(active_epics),
    }

    return json.dumps(result, indent=2)