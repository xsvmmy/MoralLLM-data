"""
API Routes for Scenario Management

Includes:
- CRUD endpoints for scenarios (DB-backed)
- Moral Machine CSV scenario lookup (random / paginated), loadable from any
  .csv file found at the project root (see /mm/datasets)
- LLM result CSV lookup (random / by response_id), for CSVs that already
  carry a per-scenario LLM judgment (see /llm/datasets)
"""

import csv
import glob
import os
import random
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

router = APIRouter(prefix="/api", tags=["scenarios"])

simulation_engine = SimulationEngine()

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_PROJECT_ROOT       = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DEFAULT_CSV_FILENAME = "filtered_responses.csv"

# ---------------------------------------------------------------------------
# CSV "kind" sniffing — distinguishes raw Moral Machine survey CSVs
# (ResponseID + Intervention, two rows per scenario) from LLM result CSVs
# (ID + LLM_Judgment, one row per scenario), by header only.
# ---------------------------------------------------------------------------

def _sniff_csv_kind(path: str) -> str:
    try:
        with open(path, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f), [])
    except Exception:
        return "unknown"
    cols = set(header)
    if "LLM_Judgment" in cols and "ID" in cols:
        return "llm_results"
    if "ResponseID" in cols and "Intervention" in cols:
        return "mm"
    return "unknown"


def _list_csvs_by_kind(kind: str) -> List[str]:
    """CSV filenames at the project root whose header matches the given kind."""
    paths = glob.glob(os.path.join(_PROJECT_ROOT, "*.csv"))
    matches = [p for p in paths if _sniff_csv_kind(p) == kind]
    return sorted(os.path.basename(p) for p in matches)


def _resolve_csv_path(filename: str) -> str:
    """Validate a filename down to a .csv basename that exists at the project root."""
    safe_name = os.path.basename(filename)
    if not safe_name.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Dataset must be a .csv file")
    path = os.path.join(_PROJECT_ROOT, safe_name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"Dataset '{safe_name}' not found")
    return path


# ---------------------------------------------------------------------------
# Moral Machine dataset cache — CSV files are parsed on first request, then
# cached by filename so switching datasets doesn't re-parse on every call.
# ---------------------------------------------------------------------------

_dataset_cache: Dict[str, Dict] = {}  # filename -> {"list": [...], "by_id": {...}}


def _list_available_datasets() -> List[str]:
    """Moral Machine CSV filenames found at the project root."""
    return _list_csvs_by_kind("mm")


def _get_dataset(filename: str) -> Dict:
    """Load (or return cached) Moral Machine scenarios for the given CSV filename."""
    safe_name = os.path.basename(filename)
    if safe_name in _dataset_cache:
        return _dataset_cache[safe_name]

    path = _resolve_csv_path(safe_name)
    try:
        scenarios = load_csv_scenarios(path, max_scenarios=50_000)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset '{safe_name}': {e}")

    data = {"list": scenarios, "by_id": {s["response_id"]: s for s in scenarios}}
    _dataset_cache[safe_name] = data
    return data


# Pre-warm the default dataset at startup so the first request isn't slow.
try:
    _default_data = _get_dataset(_DEFAULT_CSV_FILENAME)
    print(f"[scenarios] Loaded {len(_default_data['list'])} CSV scenarios from {_DEFAULT_CSV_FILENAME}")
except Exception as _e:
    print(f"[scenarios] Warning: could not load default CSV scenarios: {_e}")


# ---------------------------------------------------------------------------
# LLM results dataset cache — same caching pattern as the MM dataset cache.
# ---------------------------------------------------------------------------

_llm_dataset_cache: Dict[str, Dict] = {}  # filename -> {"list": [...], "by_id": {...}}


def _list_llm_datasets() -> List[str]:
    """LLM result CSV filenames found at the project root."""
    return _list_csvs_by_kind("llm_results")


def _get_llm_dataset(filename: str) -> Dict:
    """Load (or return cached) LLM results for the given CSV filename."""
    safe_name = os.path.basename(filename)
    if safe_name in _llm_dataset_cache:
        return _llm_dataset_cache[safe_name]

    path = _resolve_csv_path(safe_name)
    try:
        results = load_llm_results(path, max_rows=50_000)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load LLM dataset '{safe_name}': {e}")

    data = {"list": results, "by_id": {r["response_id"]: r for r in results}}
    _llm_dataset_cache[safe_name] = data
    return data


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
# Moral Machine CSV Scenario Endpoints
# ===========================================================================

@router.get("/mm/datasets")
async def list_mm_datasets():
    """CSV filenames available at the project root to load scenarios from."""
    return {"datasets": _list_available_datasets()}


@router.get("/mm/scenarios")
async def list_mm_scenarios(skip: int = 0, limit: int = 50, dataset: str = _DEFAULT_CSV_FILENAME):
    data = _get_dataset(dataset)
    if not data["list"]:
        raise HTTPException(status_code=503, detail="CSV scenario data not available")
    return data["list"][skip: skip + limit]


@router.get("/mm/scenarios/random")
async def get_random_mm_scenario(dataset: str = _DEFAULT_CSV_FILENAME):
    data = _get_dataset(dataset)
    if not data["list"]:
        raise HTTPException(status_code=503, detail="CSV scenario data not available")
    return random.choice(data["list"])


# ===========================================================================
# LLM Result CSV Endpoints
# ===========================================================================

@router.get("/llm/datasets")
async def list_llm_datasets():
    """CSV filenames available at the project root carrying LLM judgments."""
    return {"datasets": _list_llm_datasets()}


@router.get("/llm/scenarios/random")
async def get_random_llm_result(dataset: str):
    data = _get_llm_dataset(dataset)
    if not data["list"]:
        raise HTTPException(status_code=503, detail="LLM result data not available")
    return random.choice(data["list"])


@router.get("/llm/scenarios/by-id")
async def get_llm_result_by_id(dataset: str, response_id: str):
    data = _get_llm_dataset(dataset)
    result = data["by_id"].get(response_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No LLM result for response_id '{response_id}' in '{os.path.basename(dataset)}'",
        )
    return result
