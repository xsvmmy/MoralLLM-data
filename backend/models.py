"""
Data models and schemas for the AV Ethics Simulator.

This module defines:
1. SQLAlchemy ORM models for database tables
2. Pydantic schemas for API request/response validation
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, Integer, String, DateTime, JSON
from pydantic import BaseModel, Field, validator
from database import Base


# ============================================================================
# SQLAlchemy ORM Models (Database Tables)
# ============================================================================

class ScenarioDB(Base):
    """
    Database model for storing ethical dilemma scenarios.
    """
    __tablename__ = "scenarios"

    id            = Column(Integer, primary_key=True, index=True)
    passengers    = Column(JSON,   nullable=False)
    pedestrians   = Column(JSON,   nullable=False)
    traffic_light = Column(String, nullable=False)
    outcome       = Column(String, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# Pydantic Schemas — Scenario CRUD
# ============================================================================

class ScenarioBase(BaseModel):
    """Base schema with common scenario fields."""
    passengers: List[str] = Field(
        ..., min_length=1, max_length=5,
        description="List of 1–5 passenger character types"
    )
    pedestrians: List[str] = Field(
        ..., min_length=1, max_length=5,
        description="List of 1–5 pedestrian character types"
    )
    traffic_light: str = Field(
        ..., pattern="^(Red|Green|None)$",
        description="Traffic light state: Red, Green, or None"
    )

    @validator('passengers', 'pedestrians')
    def validate_character_list(cls, v):
        if not v:
            raise ValueError('At least one character must be provided')
        if len(v) > 5:
            raise ValueError('Maximum 5 characters allowed')
        return v


class ScenarioCreate(ScenarioBase):
    pass


class ScenarioUpdate(BaseModel):
    passengers:    Optional[List[str]] = Field(None, min_length=1, max_length=5)
    pedestrians:   Optional[List[str]] = Field(None, min_length=1, max_length=5)
    traffic_light: Optional[str]       = Field(None, pattern="^(Red|Green|None)$")
    outcome:       Optional[str]       = Field(None, pattern="^(stay|swerve)$")


class ScenarioResponse(ScenarioBase):
    id:         int
    outcome:    Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SimulationOutcome(BaseModel):
    outcome_choice: str = Field(..., pattern="^(stay|swerve)$")
    harmed_group:   str = Field(..., pattern="^(passengers|pedestrians)$")
    harmed_count:   int = Field(..., ge=0)
    scenario_id:    int


class CharacterType(BaseModel):
    name:        str
    category:    str
    description: str
