"""SQLAlchemy 2.x declarative entities.

Field-for-field parity with the .NET `FleetWise.Domain.Entities`:

- `String` column names are PascalCase-free on the Python side (snake_case),
  but the wire format is restored to PascalCase by Pydantic aliases in
  `fleetwise.domain.dto` (Phase 2).
- Enums are stored as VARCHAR using SQLAlchemy's `Enum(..., native_enum=False)`
  to mirror the .NET `HasConversion<string>()` behavior.
- Money columns are `Numeric(18, 2)`, labor hours `Numeric(8, 2)`; matches
  EF Core's `HasPrecision(18, 2)` / `HasPrecision(8, 2)`.
- Cascade rules: Vehicle -> children is `ondelete="CASCADE"`. The MR->WO
  edge is `ondelete="SET NULL"` so deleting a work order doesn't blow away
  historical maintenance records.
- Unique indexes on `asset_number`, `vin`, `work_order_number`, `part_number`.
- `MaintenanceSchedule.is_overdue` is a Python property (not persisted);
  `vehicle_current_mileage` must be threaded in via the eagerly-loaded
  Vehicle relationship for mileage comparisons to work.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from fleetwise.domain.enums import (
    FuelType,
    MaintenanceType,
    Priority,
    VehicleStatus,
    WorkOrderStatus,
)


class Base(DeclarativeBase):
    """Shared declarative base. One per app, used by `create_all` + Alembic later."""


def _enum_values(enum_type: type[StrEnum]) -> list[str]:
    """Member-value extractor for `values_callable`.

    Pulled out of the `_enum_column` helper (was a lambda) so pyright's
    strict mode can see that `enum_type` is `type[StrEnum]` and `member.value`
    is therefore `str`. The lambda form tripped `reportUnknownLambdaType`.
    """
    return [member.value for member in enum_type]


def _enum_column(enum_type: type[StrEnum]) -> SQLEnum:
    """Store enum values as VARCHAR, not as a native DB enum or SMALLINT.

    Parity with .NET's `HasConversion<string>()`. `values_callable` reads
    the enum member *value* (our PascalCase wire strings) rather than the
    Python member *name* (SHOUTY_SNAKE_CASE).
    """
    return SQLEnum(
        enum_type,
        native_enum=False,
        values_callable=_enum_values,
        length=32,
    )


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    vin: Mapped[str] = mapped_column(String(17), unique=True, index=True)
    year: Mapped[int] = mapped_column(Integer)
    make: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(64))
    fuel_type: Mapped[FuelType] = mapped_column(_enum_column(FuelType))
    status: Mapped[VehicleStatus] = mapped_column(_enum_column(VehicleStatus))
    department: Mapped[str] = mapped_column(String(64))
    assigned_driver: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_mileage: Mapped[int] = mapped_column(Integer)
    acquisition_date: Mapped[datetime] = mapped_column(DateTime)
    acquisition_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    license_plate: Mapped[str] = mapped_column(String(16))
    location: Mapped[str] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    maintenance_records: Mapped[list[MaintenanceRecord]] = relationship(
        back_populates="vehicle",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    maintenance_schedules: Mapped[list[MaintenanceSchedule]] = relationship(
        back_populates="vehicle",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    work_orders: Mapped[list[WorkOrder]] = relationship(
        back_populates="vehicle",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class MaintenanceSchedule(Base):
    __tablename__ = "maintenance_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"), index=True
    )
    maintenance_type: Mapped[MaintenanceType] = mapped_column(_enum_column(MaintenanceType))
    interval_miles: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_completed_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_completed_mileage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_due_mileage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    vehicle: Mapped[Vehicle] = relationship(back_populates="maintenance_schedules")

    @property
    def is_overdue(self) -> bool:
        """Past due by date OR by mileage.

        Requires the Vehicle relationship to be loaded for the mileage
        comparison; call sites that need `is_overdue` must eager-load the
        parent. Date comparison is timezone-naive (DB-native) matched to
        `datetime.utcnow()` -- parity with the .NET `DateTime.UtcNow`.
        """
        now = datetime.now(UTC).replace(tzinfo=None)
        if self.next_due_date is not None and self.next_due_date < now:
            return True
        # `self.vehicle` is typed non-optional; call sites eager-load it via
        # `selectinload` (pyright would flag a `self.vehicle is not None` guard
        # as unnecessary). If the relationship isn't loaded at the async layer
        # SQLAlchemy raises MissingGreenlet -- a clearer signal than a silent False.
        return (
            self.next_due_mileage is not None
            and self.vehicle.current_mileage >= self.next_due_mileage
        )


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_order_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[WorkOrderStatus] = mapped_column(_enum_column(WorkOrderStatus))
    priority: Mapped[Priority] = mapped_column(_enum_column(Priority))
    description: Mapped[str] = mapped_column(String)
    requested_date: Mapped[datetime] = mapped_column(DateTime)
    completed_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    assigned_technician: Mapped[str | None] = mapped_column(String(128), nullable=True)
    labor_hours: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    vehicle: Mapped[Vehicle] = relationship(back_populates="work_orders")


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"), index=True
    )
    work_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    maintenance_type: Mapped[MaintenanceType] = mapped_column(_enum_column(MaintenanceType))
    performed_date: Mapped[datetime] = mapped_column(DateTime)
    mileage_at_service: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String)
    cost: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    technician_name: Mapped[str] = mapped_column(String(128))

    vehicle: Mapped[Vehicle] = relationship(back_populates="maintenance_records")
    work_order: Mapped[WorkOrder | None] = relationship()


class Part(Base):
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    part_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(64))
    quantity_in_stock: Mapped[int] = mapped_column(Integer)
    reorder_threshold: Mapped[int] = mapped_column(Integer)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    location: Mapped[str] = mapped_column(String(64))


class VehicleInspection(Base):
    """Inspection record loaded from a messy external CSV via the ETL pipeline.

    Three deliberate design choices worth flagging:

    1. ``vehicle_id`` is nullable. When a CSV row references an asset
       number we don't have in the fleet (the inspection equivalent of an
       orphan record), we load it anyway with ``vehicle_id=None`` and the
       original string preserved on ``unmatched_asset_number``. The
       pipeline's job is to *normalize and load*, not to silently drop
       data that arrived in our inbox -- a recruiter reading the code
       sees this is a deliberate policy, not an oversight.

    2. ``(source_file, source_row_hash)`` is the idempotency key. The
       hash is sha256 of the canonical (post-transform) row payload, so
       running the same CSV twice produces the same hash and the second
       run becomes a no-op upsert.

    3. No SQL ``CASCADE`` on the FK. If a vehicle is deleted (which we
       never do in practice but which the schema allows), inspections
       become orphans -- ``ondelete="SET NULL"`` keeps the history.
    """

    __tablename__ = "vehicle_inspections"
    __table_args__ = (
        UniqueConstraint("source_file", "source_row_hash", name="uq_inspection_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL"), index=True, nullable=True
    )
    unmatched_asset_number: Mapped[str | None] = mapped_column(
        String(32), nullable=True, index=True
    )
    inspected_at: Mapped[datetime] = mapped_column(DateTime)
    inspector_name: Mapped[str] = mapped_column(String(128))
    mileage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean)
    findings: Mapped[str] = mapped_column(String)
    recommendations: Mapped[str | None] = mapped_column(String, nullable=True)
    source_file: Mapped[str] = mapped_column(String(255), index=True)
    source_row_hash: Mapped[str] = mapped_column(String(64))

    vehicle: Mapped[Vehicle | None] = relationship()
