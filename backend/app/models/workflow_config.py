"""Workflow definitions configurable en base (courrier, RDV)."""

from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    entity_type = Column(String(32), nullable=False, index=True)  # mail, appointment
    subtype = Column(String(32), nullable=True, index=True)  # inbound, outbound, internal
    name = Column(String(128), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    steps = relationship(
        "WorkflowStep",
        back_populates="definition",
        cascade="all, delete-orphan",
        order_by="WorkflowStep.sort_order",
    )
    transitions = relationship(
        "WorkflowTransition",
        back_populates="definition",
        cascade="all, delete-orphan",
    )


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    definition_id = Column(UUID(as_uuid=True), ForeignKey("workflow_definitions.id"), nullable=False)
    step_key = Column(String(64), nullable=False, index=True)
    label = Column(String(255), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)

    definition = relationship("WorkflowDefinition", back_populates="steps")
    outgoing_transitions = relationship(
        "WorkflowTransition",
        foreign_keys="WorkflowTransition.from_step_id",
        back_populates="from_step",
    )


class WorkflowTransition(Base):
    __tablename__ = "workflow_transitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    definition_id = Column(UUID(as_uuid=True), ForeignKey("workflow_definitions.id"), nullable=False)
    from_step_id = Column(UUID(as_uuid=True), ForeignKey("workflow_steps.id"), nullable=False)
    to_step_id = Column(UUID(as_uuid=True), ForeignKey("workflow_steps.id"), nullable=False)
    action_key = Column(String(64), nullable=False, index=True)
    label = Column(String(255), nullable=True)
    requires_assignee = Column(Boolean, nullable=False, default=False)

    definition = relationship("WorkflowDefinition", back_populates="transitions")
    from_step = relationship(
        "WorkflowStep",
        foreign_keys=[from_step_id],
        back_populates="outgoing_transitions",
    )
    to_step = relationship("WorkflowStep", foreign_keys=[to_step_id])
    permissions = relationship(
        "WorkflowTransitionPermission",
        back_populates="transition",
        cascade="all, delete-orphan",
    )


class WorkflowTransitionPermission(Base):
    __tablename__ = "workflow_transition_permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    transition_id = Column(UUID(as_uuid=True), ForeignKey("workflow_transitions.id"), nullable=False)
    permission_key = Column(String(128), nullable=False)

    transition = relationship("WorkflowTransition", back_populates="permissions")
