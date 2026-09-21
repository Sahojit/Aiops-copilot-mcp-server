import os
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_name = Column(String, nullable=False)
    opened_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    root_cause = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    cascade_risk = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="open")
    closed_at = Column(DateTime, nullable=True)


class Commit(Base):
    __tablename__ = "commits"

    sha = Column(String, primary_key=True)
    service_name = Column(String, nullable=False)
    author = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    diff_summary = Column(String, nullable=True)
    risk_score = Column(Float, nullable=True)
    top_factors = Column(JSONB, nullable=True)


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tool_name = Column(String, nullable=False)
    caller_id = Column(String, nullable=False)
    args = Column(JSONB, nullable=True)
    result_summary = Column(String, nullable=True)
    latency_ms = Column(Float, nullable=True)
    cost_usd = Column(Float, nullable=False, default=0.0)
    status = Column(String, nullable=False, default="success")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Mitigation(Base):
    __tablename__ = "mitigations"

    draft_id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    proposed_action = Column(String, nullable=False)
    status = Column(String, nullable=False, default="drafted")
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)


def get_engine():
    database_url = os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/aiops_copilot"
    )
    return create_engine(database_url)


def get_session_factory(engine=None):
    engine = engine or get_engine()
    return sessionmaker(bind=engine)
