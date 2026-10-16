"""
Modules package for AV Ethics Simulator.

This package contains core modules for:
- scenario_config: Scenario validation and configuration
- simulation_logic: Decision-making and simulation engine
- data_storage: Database operations and persistence
"""

from .scenario_config import (
    VALID_CHARACTERS,
    CHARACTER_CATEGORIES,
    validate_scenario,
    get_character_info
)

from .simulation_logic import SimulationEngine

from .data_storage import (
    ScenarioStorage,
    export_scenarios_json,
    get_storage_statistics
)

__all__ = [
    'VALID_CHARACTERS',
    'CHARACTER_CATEGORIES',
    'validate_scenario',
    'get_character_info',
    'SimulationEngine',
    'ScenarioStorage',
    'export_scenarios_json',
    'get_storage_statistics'
]
