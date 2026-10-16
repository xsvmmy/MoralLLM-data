"""
Simulation Logic Module

This module contains the core decision-making logic for the AV ethical simulator.
Given a scenario and a chosen action ("stay" or "swerve"), determines which
group is harmed/saved and by how much.
"""

from typing import Dict, List


class SimulationEngine:
    """
    Core simulation engine for ethical dilemma scenarios.

    Processes a chosen action ("stay" or "swerve") against a scenario and
    determines which group is harmed/saved and by how much.
    """

    def __init__(self):
        """Initialize simulation engine."""
        self.action_space = ["stay", "swerve"]

    def simulate_outcome(self, scenario: Dict, chosen_action: str) -> Dict:
        """
        Simulate the outcome of a decision.

        Args:
            scenario: Dictionary containing passengers, pedestrians, traffic_light
            chosen_action: "stay" or "swerve"

        Returns:
            Dictionary with outcome details (harmed_group, harmed_count, etc.)
        """
        passengers = scenario["passengers"]
        pedestrians = scenario["pedestrians"]
        traffic_light = scenario["traffic_light"]

        # Determine which group was harmed based on action
        if chosen_action == "stay":
            harmed_group = "pedestrians"
            harmed_count = len(pedestrians)
            saved_group = "passengers"
            saved_count = len(passengers)
        else:  # swerve
            harmed_group = "passengers"
            harmed_count = len(passengers)
            saved_group = "pedestrians"
            saved_count = len(pedestrians)

        return {
            "outcome_choice": chosen_action,
            "harmed_group": harmed_group,
            "harmed_count": harmed_count,
            "saved_group": saved_group,
            "saved_count": saved_count,
            "traffic_light_state": traffic_light
        }

    def get_action_description(self, action: str) -> str:
        """
        Get human-readable description of an action.

        Args:
            action: "stay" or "swerve"

        Returns:
            Description string
        """
        descriptions = {
            "stay": "Vehicle stays in lane and continues forward",
            "swerve": "Vehicle swerves to avoid pedestrians and hits barrier"
        }
        return descriptions.get(action, "Unknown action")


# ============================================================================
# Utility Functions
# ============================================================================

def get_available_actions() -> List[str]:
    """Get list of available actions."""
    return ["stay", "swerve"]


def get_simulation_summary(scenarios: List[Dict]) -> Dict:
    """
    Generate summary statistics from multiple scenarios.

    Useful for analyzing patterns in decisions/outcomes.

    Args:
        scenarios: List of scenario dictionaries with outcomes

    Returns:
        Summary statistics dictionary
    """
    if not scenarios:
        return {}

    total = len(scenarios)
    stay_count = sum(1 for s in scenarios if s.get("outcome") == "stay")
    swerve_count = sum(1 for s in scenarios if s.get("outcome") == "swerve")

    return {
        "total_scenarios": total,
        "stay_percentage": (stay_count / total * 100) if total > 0 else 0,
        "swerve_percentage": (swerve_count / total * 100) if total > 0 else 0,
        "avg_passengers": sum(len(s.get("passengers", [])) for s in scenarios) / total,
        "avg_pedestrians": sum(len(s.get("pedestrians", [])) for s in scenarios) / total,
    }
