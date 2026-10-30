"""
API Routes for Scenario Management

Includes:
- CRUD endpoints for scenarios (DB-backed)
- Moral Machine CSV scenario lookup (random / paginated), loadable from any
  .csv file in human-data/ (see /mm/datasets)
- LLM result CSV lookup (random / by response_id), loadable from any .csv
  file in LLM-data/ (see /llm/datasets)
- LLM debate result CSV lookup (random / by response_id), loadable from any
  .csv file in LLM-debate-data/ (see /debate/datasets)
"""

import glob
import os
import random
import re
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import (
    ScenarioCreate,
    ScenarioUpdate,
    ScenarioResponse,
    SimulationOutcome,
    CharacterType,
)
from modules.scenario_config import validate_scenario, get_character_info, VALID_CHARACTERS
from modules.data_storage import ScenarioStorage
from modules.simulation_logic import SimulationEngine
from modules.csv_loader import load_csv_scenarios
from modules.llm_results_loader import load_llm_results
from modules.llm_debate_loader import load_debate_results

router = APIRouter(prefix="/api", tags=["scenarios"])

simulation_engine = SimulationEngine()

# ---------------------------------------------------------------------------
# Path constants — each kind of CSV lives in its own project-root subfolder.
# ---------------------------------------------------------------------------

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HUMAN_DATA_DIR  = os.path.join(_PROJECT_ROOT, "human-data")
_LLM_DATA_DIR    = os.path.join(_PROJECT_ROOT, "LLM-data")
_DEBATE_DATA_DIR = os.path.join(_PROJECT_ROOT, "LLM-debate-data")

_DEFAULT_CSV_FILENAME = "filtered_responses.csv"


class _DatasetGroup:
    """
    A named group of same-shaped CSVs living in one subdirectory.

    Parses a CSV on first request via `loader_fn(path, max_rows)` — every
    loader in this app takes (path, max_rows_or_max_scenarios) positionally
    — then caches the parsed list/by-id map for the group's lifetime.
    """

    def __init__(self, label: str, dir_path: str, loader_fn, max_rows: int = 50_000):
        self.label     = label
        self.dir_path  = dir_path
        self.loader_fn = loader_fn
        self.max_rows  = max_rows
        self._cache: Dict[str, Dict] = {}

    def list_datasets(self) -> List[str]:
        """CSV filenames found directly in this group's directory."""
        paths = glob.glob(os.path.join(self.dir_path, "*.csv"))
        return sorted(os.path.basename(p) for p in paths)

    def _resolve_path(self, filename: str) -> str:
        """Validate a filename down to a .csv basename that exists in this group's directory."""
        safe_name = os.path.basename(filename)
        if not safe_name.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Dataset must be a .csv file")
        path = os.path.join(self.dir_path, safe_name)
        if not os.path.isfile(path):
            raise HTTPException(
                status_code=404,
                detail=f"Dataset '{safe_name}' not found in {self.label}",
            )
        return path

    def get(self, filename: str) -> Dict:
        """Load (or return cached) parsed rows for the given CSV filename."""
        safe_name = os.path.basename(filename)
        if safe_name in self._cache:
            return self._cache[safe_name]

        path = self._resolve_path(safe_name)
        try:
            items = self.loader_fn(path, self.max_rows)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to load {self.label} dataset '{safe_name}': {e}",
            )

        # Round number lives only in the filename (e.g. "..._round2_all.csv"),
        # not as a CSV column — stamp it onto every row so the frontend can
        # show it next to the model name.
        round_match = re.search(r"round(\d+)", safe_name, re.IGNORECASE)
        round_num = int(round_match.group(1)) if round_match else None
        for item in items:
            item["round"] = round_num

        data = {"list": items, "by_id": {i["response_id"]: i for i in items}}
        self._cache[safe_name] = data
        return data


human_data  = _DatasetGroup("Human",      _HUMAN_DATA_DIR,  load_csv_scenarios)
llm_data    = _DatasetGroup("LLM",        _LLM_DATA_DIR,    load_llm_results)
debate_data = _DatasetGroup("LLM Debate", _DEBATE_DATA_DIR, load_debate_results)


def _choice_dispersion(data: Dict, field: str) -> Dict:
    """
    Tally a dataset group's stay/swerve/parse_error values for one field
    (e.g. "llm_judgment" or "debate_judgment") across every row, and express
    it as a stay/swerve percentage split — how dispersed vs. one-sided this
    model's (or debate's) judgments are across the whole dataset.

    parse_error rows are counted but excluded from the stay/swerve
    percentages, since they're not a real verdict either way.
    """
    counts = {"stay": 0, "swerve": 0, "parse_error": 0}
    for item in data["list"]:
        v = item.get(field)
        if v in counts:
            counts[v] += 1

    total_verdicts = counts["stay"] + counts["swerve"]
    stay_pct   = round(counts["stay"]   / total_verdicts * 100, 1) if total_verdicts else 0.0
    swerve_pct = round(counts["swerve"] / total_verdicts * 100, 1) if total_verdicts else 0.0

    return {
        "total":             len(data["list"]),
        "stay_count":        counts["stay"],
        "swerve_count":      counts["swerve"],
        "parse_error_count": counts["parse_error"],
        "stay_pct":          stay_pct,
        "swerve_pct":        swerve_pct,
    }


# Pre-warm the default Human dataset at startup so the first request isn't slow.
try:
    _default_data = human_data.get(_DEFAULT_CSV_FILENAME)
    print(f"[scenarios] Loaded {len(_default_data['list'])} CSV scenarios from {_DEFAULT_CSV_FILENAME}")
except Exception as _e:
    print(f"[scenarios] Warning: could not load default CSV scenarios: {_e}")


# ===========================================================================
# Character & Scenario CRUD
# ===========================================================================

@router.get("/characters", response_model=List[CharacterType])
async def get_characters():
    return get_character_info()


@router.get("/scenarios", response_model=List[ScenarioResponse])
async def list_scenarios(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return ScenarioStorage.get_all_scenarios(db, skip=skip, limit=limit)


@router.post("/scenarios", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_scenario(scenario: ScenarioCreate, db: Session = Depends(get_db)):
    result = validate_scenario(scenario.passengers, scenario.pedestrians, scenario.traffic_light)
    if not result["valid"]:
        raise HTTPException(status_code=400, detail={"message": "Invalid scenario", "errors": result["errors"]})
    return ScenarioStorage.create_scenario(db, scenario)


@router.get("/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(scenario_id: int, db: Session = Depends(get_db)):
    sc = ScenarioStorage.get_scenario(db, scenario_id)
    if not sc:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    return sc


@router.put("/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(scenario_id: int, scenario_update: ScenarioUpdate, db: Session = Depends(get_db)):
    existing = ScenarioStorage.get_scenario(db, scenario_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    passengers    = scenario_update.passengers    or existing.passengers
    pedestrians   = scenario_update.pedestrians   or existing.pedestrians
    traffic_light = scenario_update.traffic_light or existing.traffic_light
    result = validate_scenario(passengers, pedestrians, traffic_light)
    if not result["valid"]:
        raise HTTPException(status_code=400, detail={"message": "Invalid update", "errors": result["errors"]})
    return ScenarioStorage.update_scenario(db, scenario_id, scenario_update)


@router.delete("/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(scenario_id: int, db: Session = Depends(get_db)):
    if not ScenarioStorage.delete_scenario(db, scenario_id):
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")


@router.post("/scenarios/{scenario_id}/simulate", response_model=SimulationOutcome)
async def simulate_scenario(scenario_id: int, action: str, db: Session = Depends(get_db)):
    if action not in ["stay", "swerve"]:
        raise HTTPException(status_code=400, detail="Action must be 'stay' or 'swerve'")
    sc = ScenarioStorage.get_scenario(db, scenario_id)
    if not sc:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    scenario_data = {"passengers": sc.passengers, "pedestrians": sc.pedestrians, "traffic_light": sc.traffic_light}
    outcome = simulation_engine.simulate_outcome(scenario_data, action)
    ScenarioStorage.update_scenario_outcome(db, scenario_id, action)
    return SimulationOutcome(
        outcome_choice=outcome["outcome_choice"],
        harmed_group=outcome["harmed_group"],
        harmed_count=outcome["harmed_count"],
        scenario_id=scenario_id,
    )


@router.get("/scenarios/{scenario_id}/outcome")
async def get_scenario_outcome(scenario_id: int, db: Session = Depends(get_db)):
    sc = ScenarioStorage.get_scenario(db, scenario_id)
    if not sc:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    if not sc.outcome:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} has not been simulated yet")
    scenario_data = {"passengers": sc.passengers, "pedestrians": sc.pedestrians, "traffic_light": sc.traffic_light}
    outcome = simulation_engine.simulate_outcome(scenario_data, sc.outcome)
    return {
        "scenario_id": scenario_id, "outcome_choice": sc.outcome,
        "harmed_group": outcome["harmed_group"], "harmed_count": outcome["harmed_count"],
        "saved_group": outcome["saved_group"],   "saved_count": outcome["saved_count"],
    }


@router.get("/statistics")
async def get_statistics(db: Session = Depends(get_db)):
    from modules.data_storage import get_storage_statistics
    return get_storage_statistics(db)


@router.get("/export/json")
async def export_scenarios(db: Session = Depends(get_db)):
    from modules.data_storage import export_scenarios_json
    count = export_scenarios_json(db)
    return {"message": f"Exported {count} scenarios to scenarios_export.json", "count": count}


# ===========================================================================
# Moral Machine CSV Scenario Endpoints — from human-data/
# ===========================================================================

@router.get("/mm/datasets")
async def list_mm_datasets():
    """CSV filenames available in human-data/ to load scenarios from."""
    return {"datasets": human_data.list_datasets()}


@router.get("/mm/scenarios")
async def list_mm_scenarios(skip: int = 0, limit: int = 50, dataset: str = _DEFAULT_CSV_FILENAME):
    data = human_data.get(dataset)
    if not data["list"]:
        raise HTTPException(status_code=503, detail="CSV scenario data not available")
    return data["list"][skip: skip + limit]


@router.get("/mm/scenarios/random")
async def get_random_mm_scenario(dataset: str = _DEFAULT_CSV_FILENAME):
    data = human_data.get(dataset)
    if not data["list"]:
        raise HTTPException(status_code=503, detail="CSV scenario data not available")
    return random.choice(data["list"])


# ===========================================================================
# LLM Result CSV Endpoints — from LLM-data/
# ===========================================================================

@router.get("/llm/datasets")
async def list_llm_datasets():
    """CSV filenames available in LLM-data/ carrying per-scenario LLM judgments."""
    return {"datasets": llm_data.list_datasets()}


@router.get("/llm/scenarios/random")
async def get_random_llm_result(dataset: str):
    data = llm_data.get(dataset)
    if not data["list"]:
        raise HTTPException(status_code=503, detail="LLM result data not available")
    return random.choice(data["list"])


@router.get("/llm/scenarios/by-id")
async def get_llm_result_by_id(dataset: str, response_id: str):
    data = llm_data.get(dataset)
    result = data["by_id"].get(response_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No LLM result for response_id '{response_id}' in '{os.path.basename(dataset)}'",
        )
    return result


@router.get("/llm/scenarios/stats")
async def get_llm_dataset_stats(dataset: str):
    """Stay/swerve dispersion for this model's judgments across its whole dataset."""
    data = llm_data.get(dataset)
    return _choice_dispersion(data, "llm_judgment")


# ===========================================================================
# LLM Debate Result CSV Endpoints — from LLM-debate-data/
# ===========================================================================

@router.get("/debate/datasets")
async def list_debate_datasets():
    """CSV filenames available in LLM-debate-data/ carrying per-scenario debate verdicts."""
    return {"datasets": debate_data.list_datasets()}


@router.get("/debate/scenarios/random")
async def get_random_debate_result(dataset: str):
    data = debate_data.get(dataset)
    if not data["list"]:
        raise HTTPException(status_code=503, detail="LLM debate result data not available")
    return random.choice(data["list"])


@router.get("/debate/scenarios/by-id")
async def get_debate_result_by_id(dataset: str, response_id: str):
    data = debate_data.get(dataset)
    result = data["by_id"].get(response_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No debate result for response_id '{response_id}' in '{os.path.basename(dataset)}'",
        )
    return result


@router.get("/debate/scenarios/stats")
async def get_debate_dataset_stats(dataset: str):
    """Stay/swerve dispersion for this debate's final verdicts across its whole dataset."""
    data = debate_data.get(dataset)
    return _choice_dispersion(data, "debate_judgment")
