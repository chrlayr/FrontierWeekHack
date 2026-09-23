import json
from pathlib import Path

from fpna_agent.tools.actuals_tool import get_actuals
from fpna_agent.tools.workload_tool import get_workload


BUDGET_FILE = Path(__file__).parent.parent / "data" / "budget.json"


def get_forecast() -> str:
    """
    Build a deterministic financial forecast from:
    - ERP actuals
    - operational workload
    - budget assumptions
    """

    # Load evidence from the two existing tools
    actuals = json.loads(get_actuals())
    workload = json.loads(get_workload())

    # Load budget and planning assumptions
    with open(BUDGET_FILE, "r", encoding="utf-8") as file:
        budget = json.load(file)

    total_actuals = actuals["total_actuals"]
    annual_budget = sum(budget["annual_budget"].values())

    external_person_days = workload["external_remaining_person_days"]
    external_day_rate = budget["external_day_rate"]

    # Deterministic forecast of remaining external workload
    remaining_external_cost = external_person_days * external_day_rate

    # Simple MVP forecast
    forecast = total_actuals + remaining_external_cost

    variance_to_budget = forecast - annual_budget
    variance_percent = (
        variance_to_budget / annual_budget * 100
        if annual_budget != 0
        else 0
    )

    result = {
        "source": [
            "erp_mock",
            "workload_mock",
            "budget_mock"
        ],
        "actuals_to_date": total_actuals,
        "annual_budget": annual_budget,
        "remaining_external_person_days": external_person_days,
        "external_day_rate": external_day_rate,
        "forecast_remaining_external_cost": remaining_external_cost,
        "forecast": forecast,
        "variance_to_budget": variance_to_budget,
        "variance_percent": round(variance_percent, 1),
        "human_review_amount": actuals["totals_by_category"].get(
            "Human Review", 0
        )
    }

    return json.dumps(result, indent=2)