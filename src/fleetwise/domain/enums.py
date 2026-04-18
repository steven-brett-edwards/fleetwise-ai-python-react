"""Domain enums.

Subclassing `StrEnum` (new in 3.11) means each member's value is the string
form the .NET edition serializes (`"Active"`, `"Diesel"`, etc.), so the
wire format stays identical and the Angular frontend works unchanged.

The `.NET` side uses `HasConversion<string>()` in EF Core's model builder,
which produces the same string-backed column. On the SQLAlchemy side this
is `SQLEnum(X, native_enum=False)` in `entities.py` -- columns hold the
enum *name* as a VARCHAR, not a SMALLINT ordinal.
"""

from enum import StrEnum


class FuelType(StrEnum):
    GASOLINE = "Gasoline"
    DIESEL = "Diesel"
    ELECTRIC = "Electric"
    HYBRID = "Hybrid"
    CNG = "CNG"


class VehicleStatus(StrEnum):
    ACTIVE = "Active"
    IN_SHOP = "InShop"
    OUT_OF_SERVICE = "OutOfService"
    RETIRED = "Retired"


class WorkOrderStatus(StrEnum):
    OPEN = "Open"
    IN_PROGRESS = "InProgress"
    AWAITING_PARTS = "AwaitingParts"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class Priority(StrEnum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class MaintenanceType(StrEnum):
    OIL_CHANGE = "OilChange"
    TIRE_ROTATION = "TireRotation"
    BRAKE_INSPECTION = "BrakeInspection"
    TRANSMISSION_SERVICE = "TransmissionService"
    AIR_FILTER = "AirFilter"
    DOT_INSPECTION = "DOTInspection"
    BATTERY_CHECK = "BatteryCheck"
    COOLANT_FLUSH = "CoolantFlush"
    EV_BATTERY_DIAGNOSTIC = "EVBatteryDiagnostic"
