"""
Scenario Configuration Module

This module handles validation and configuration of ethical dilemma scenarios.
It defines available character types and validates scenario configurations.

Future RL Integration:
- Add character attribute encoding (age, gender, social status, etc.)
- Implement state vector generation for RL agent input
- Add scenario complexity metrics for curriculum learning
"""

from typing import List, Dict
from pydantic import ValidationError


# Valid character types that can be placed in scenarios
VALID_CHARACTERS = [
    "Man",
    "Woman",
    "Pregnant",
    "Stroller",
    "OldMan",
    "OldWoman",
    "Boy",
    "Girl",
    "Homeless",
    "LargeWoman",
    "LargeMan",
    "Criminal",
    "MaleExecutive",
    "FemaleExecutive",
    "FemaleAthlete",
    "MaleAthlete",
    "FemaleDoctor",
    "MaleDoctor",
    "Dog",
    "Cat",
    "Barricade"
]

# Character categories for semantic grouping
CHARACTER_CATEGORIES = {
    "adults": ["Man", "Woman", "Homeless", "LargeWoman", "LargeMan", "Criminal"],
    "elderly": ["OldMan", "OldWoman"],
    "children": ["Boy", "Girl", "Stroller"],
    "special": ["Pregnant"],
    "professionals": ["MaleExecutive", "FemaleExecutive", "FemaleAthlete",
                     "MaleAthlete", "FemaleDoctor", "MaleDoctor"],
    "animals": ["Dog", "Cat"],
    "obstacles": ["Barricade"]
}


def get_character_info() -> List[Dict[str, str]]:
    """
    Get information about all available character types.

    Returns:
        List of dictionaries containing character name, category, and description
    """
    character_info = []

    for category, characters in CHARACTER_CATEGORIES.items():
        for char in characters:
            character_info.append({
                "name": char,
                "category": category,
                "description": f"{char} character type"
            })

    return character_info


def validate_characters(characters: List[str]) -> bool:
    """
    Validate that all characters in the list are valid types.

    Args:
        characters: List of character type names

    Returns:
        True if all characters are valid, False otherwise
    """
    return all(char in VALID_CHARACTERS for char in characters)


def validate_scenario(passengers: List[str], pedestrians: List[str],
                      traffic_light: str) -> Dict[str, any]:
    """
    Validate a complete scenario configuration.

    Args:
        passengers: List of passenger character types (1-5)
        pedestrians: List of pedestrian character types (1-5)
        traffic_light: Traffic light state ("Red", "Green", or "None")

    Returns:
        Dictionary with validation result and any error messages
    """
    errors = []

    # Validate passenger count
    if not passengers or len(passengers) < 1:
        errors.append("At least 1 passenger required")
    elif len(passengers) > 5:
        errors.append("Maximum 5 passengers allowed")

    # Validate pedestrian count
    if not pedestrians or len(pedestrians) < 1:
        errors.append("At least 1 pedestrian required")
    elif len(pedestrians) > 5:
        errors.append("Maximum 5 pedestrians allowed")

    # Validate character types
    if not validate_characters(passengers):
        invalid = [p for p in passengers if p not in VALID_CHARACTERS]
        errors.append(f"Invalid passenger types: {invalid}")

    if not validate_characters(pedestrians):
        invalid = [p for p in pedestrians if p not in VALID_CHARACTERS]
        errors.append(f"Invalid pedestrian types: {invalid}")

    # Validate traffic light
    if traffic_light not in ["Red", "Green", "None"]:
        errors.append("Traffic light must be 'Red', 'Green', or 'None'")

    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


# ============================================================================
# Future RL Integration Functions (Placeholders)
# ============================================================================

def encode_character_features(character: str) -> Dict[str, any]:
    """
    TODO: Encode character attributes for RL state representation.

    This function will convert character types into feature vectors
    for the RL agent. Features might include:
    - Age group (child, adult, elderly)
    - Gender
    - Social status indicators
    - Vulnerability factors

    Args:
        character: Character type name

    Returns:
        Dictionary of character features
    """
    # Placeholder implementation
    return {
        "character_type": character,
        "age_group": "unknown",
        "social_status": "unknown"
    }


def calculate_scenario_complexity(passengers: List[str],
                                  pedestrians: List[str]) -> float:
    """
    TODO: Calculate scenario complexity metric for curriculum learning.

    More complex scenarios might have:
    - More characters
    - Greater diversity of character types
    - Conflicting ethical considerations

    This can be used to gradually increase training difficulty.

    Args:
        passengers: List of passenger character types
        pedestrians: List of pedestrian character types

    Returns:
        Complexity score (0.0 to 1.0)
    """
    # Placeholder: simple count-based complexity
    total_characters = len(passengers) + len(pedestrians)
    return min(total_characters / 10.0, 1.0)
