"""
Data Storage Module

This module handles database operations for scenarios.
Provides CRUD operations and data export functionality.

Future RL Integration:
- Store training episodes and trajectories
- Export data in formats compatible with RL frameworks
- Track agent versions and performance metrics
"""

from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
import json

from models import ScenarioDB, ScenarioCreate, ScenarioUpdate


class ScenarioStorage:
    """
    Data access layer for scenario persistence.

    Handles all database operations for scenarios.
    """

    @staticmethod
    def create_scenario(db: Session, scenario: ScenarioCreate) -> ScenarioDB:
        """
        Create and save a new scenario.

        Args:
            db: Database session
            scenario: Scenario data to create

        Returns:
            Created scenario database model
        """
        db_scenario = ScenarioDB(
            passengers=scenario.passengers,
            pedestrians=scenario.pedestrians,
            traffic_light=scenario.traffic_light,
            outcome=None  # No outcome until simulation is run
        )
        db.add(db_scenario)
        db.commit()
        db.refresh(db_scenario)
        return db_scenario

    @staticmethod
    def get_scenario(db: Session, scenario_id: int) -> Optional[ScenarioDB]:
        """
        Retrieve a scenario by ID.

        Args:
            db: Database session
            scenario_id: ID of scenario to retrieve

        Returns:
            Scenario model or None if not found
        """
        return db.query(ScenarioDB).filter(ScenarioDB.id == scenario_id).first()

    @staticmethod
    def get_all_scenarios(db: Session, skip: int = 0,
                         limit: int = 100) -> List[ScenarioDB]:
        """
        Retrieve all scenarios with pagination.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of scenario models
        """
        return db.query(ScenarioDB)\
            .order_by(desc(ScenarioDB.created_at))\
            .offset(skip)\
            .limit(limit)\
            .all()

    @staticmethod
    def update_scenario(db: Session, scenario_id: int,
                       scenario_update: ScenarioUpdate) -> Optional[ScenarioDB]:
        """
        Update an existing scenario.

        Args:
            db: Database session
            scenario_id: ID of scenario to update
            scenario_update: Updated scenario data

        Returns:
            Updated scenario model or None if not found
        """
        db_scenario = ScenarioStorage.get_scenario(db, scenario_id)
        if not db_scenario:
            return None

        # Update only provided fields
        update_data = scenario_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_scenario, field, value)

        db.commit()
        db.refresh(db_scenario)
        return db_scenario

    @staticmethod
    def update_scenario_outcome(db: Session, scenario_id: int,
                               outcome: str) -> Optional[ScenarioDB]:
        """
        Update the outcome of a scenario after simulation.

        Args:
            db: Database session
            scenario_id: ID of scenario
            outcome: Outcome choice ("stay" or "swerve")

        Returns:
            Updated scenario model or None if not found
        """
        db_scenario = ScenarioStorage.get_scenario(db, scenario_id)
        if not db_scenario:
            return None

        db_scenario.outcome = outcome
        db.commit()
        db.refresh(db_scenario)
        return db_scenario

    @staticmethod
    def delete_scenario(db: Session, scenario_id: int) -> bool:
        """
        Delete a scenario.

        Args:
            db: Database session
            scenario_id: ID of scenario to delete

        Returns:
            True if deleted, False if not found
        """
        db_scenario = ScenarioStorage.get_scenario(db, scenario_id)
        if not db_scenario:
            return False

        db.delete(db_scenario)
        db.commit()
        return True

    @staticmethod
    def get_scenarios_by_outcome(db: Session, outcome: str) -> List[ScenarioDB]:
        """
        Get all scenarios with a specific outcome.

        Useful for analyzing decision patterns.

        Args:
            db: Database session
            outcome: Outcome to filter by ("stay" or "swerve")

        Returns:
            List of matching scenarios
        """
        return db.query(ScenarioDB)\
            .filter(ScenarioDB.outcome == outcome)\
            .all()

    @staticmethod
    def get_scenario_count(db: Session) -> int:
        """
        Get total number of scenarios.

        Args:
            db: Database session

        Returns:
            Count of scenarios
        """
        return db.query(ScenarioDB).count()


# ============================================================================
# Data Export Functions
# ============================================================================

def export_scenarios_json(db: Session, output_path: str = "scenarios_export.json"):
    """
    Export all scenarios to JSON file.

    Useful for:
    - Data backup
    - Offline RL training data preparation
    - Analysis in external tools

    Args:
        db: Database session
        output_path: Path to output JSON file
    """
    scenarios = ScenarioStorage.get_all_scenarios(db, limit=10000)

    export_data = []
    for scenario in scenarios:
        export_data.append({
            "id": scenario.id,
            "passengers": scenario.passengers,
            "pedestrians": scenario.pedestrians,
            "traffic_light": scenario.traffic_light,
            "outcome": scenario.outcome,
            "created_at": scenario.created_at.isoformat()
        })

    with open(output_path, 'w') as f:
        json.dump(export_data, f, indent=2)

    return len(export_data)


def export_for_rl_training(db: Session, output_path: str = "rl_training_data.json"):
    """
    TODO: Export scenarios in format suitable for RL training.

    This function will prepare data for offline RL training:
    - Convert scenarios to state vectors
    - Include action and reward information
    - Format for compatibility with RL frameworks (e.g., PyTorch, TensorFlow)

    Args:
        db: Database session
        output_path: Path to output file

    Returns:
        Number of training examples exported
    """
    # Placeholder implementation
    scenarios = ScenarioStorage.get_all_scenarios(db, limit=10000)

    training_data = []
    for scenario in scenarios:
        if scenario.outcome:  # Only include simulated scenarios
            # TODO: Convert to RL training format
            training_data.append({
                "state": [],  # TODO: encode_state(scenario)
                "action": 0 if scenario.outcome == "stay" else 1,
                "reward": 0.0,  # TODO: calculate_reward()
                "next_state": [],
                "done": True
            })

    with open(output_path, 'w') as f:
        json.dump(training_data, f, indent=2)

    return len(training_data)


def get_storage_statistics(db: Session) -> Dict:
    """
    Get statistics about stored data.

    Args:
        db: Database session

    Returns:
        Dictionary with storage statistics
    """
    total = ScenarioStorage.get_scenario_count(db)
    stay_outcomes = len(ScenarioStorage.get_scenarios_by_outcome(db, "stay"))
    swerve_outcomes = len(ScenarioStorage.get_scenarios_by_outcome(db, "swerve"))
    unsimulated = total - stay_outcomes - swerve_outcomes

    return {
        "total_scenarios": total,
        "simulated_scenarios": stay_outcomes + swerve_outcomes,
        "unsimulated_scenarios": unsimulated,
        "stay_outcomes": stay_outcomes,
        "swerve_outcomes": swerve_outcomes
    }
