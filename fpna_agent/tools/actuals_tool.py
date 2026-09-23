import json
from pathlib import Path
from collections import defaultdict


DATA_FILE = Path(__file__).parent.parent / "data" / "actuals.json"


def get_actuals() -> str:
    """
    Map ERP transactions to FP&A categories.

    MVP source: synthetic ERP transactions.
    Future source: ERP / SAP API.
    """

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        transactions = json.load(file)

    mapped_transactions = []
    totals_by_category = defaultdict(float)

    for tx in transactions:
        description = tx["description"].lower()
        vendor = tx["vendor"].lower()

        # Default: uncertain transaction
        category = "Human Review"
        confidence = "low"
        reason = "Insufficient information for reliable automatic mapping."

        # Rule 1: Cloud services
        if "cloud platform subscription" in description:
            category = "Cloud Services"
            confidence = "high"
            reason = "Description identifies a recurring cloud platform subscription."

        # Rule 2: External development
        elif "external development" in description:
            category = "External Development"
            confidence = "high"
            reason = "Description explicitly identifies external development work."

        # Rule 3: ERP integration consulting
        elif "erp integration" in description and "consulting" in description:
            category = "External Consulting"
            confidence = "high"
            reason = "Description identifies consulting work for ERP integration."

        mapped_transactions.append(
            {
                "transaction_id": tx["transaction_id"],
                "amount": tx["amount"],
                "category": category,
                "confidence": confidence,
                "reason": reason,
                "source": "erp_mock"
            }
        )

        totals_by_category[category] += tx["amount"]

    result = {
        "source": "erp_mock",
        "total_actuals": sum(tx["amount"] for tx in transactions),
        "totals_by_category": dict(totals_by_category),
        "transactions": mapped_transactions
    }

    return json.dumps(result, indent=2)