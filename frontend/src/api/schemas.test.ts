import { describe, expect, it } from 'vitest'
import {
  ChatResponseSchema,
  FleetSummarySchema,
  MaintenanceRecordSchema,
  MaintenanceScheduleItemSchema,
  VehicleSchema,
  WorkOrderSchema,
} from './schemas'

describe('VehicleSchema', () => {
  const canonical = {
    Id: 1,
    AssetNumber: 'PW-001',
    Vin: '1FTEX1CM8HKD12345',
    Year: 2019,
    Make: 'Ford',
    Model: 'F-150',
    FuelType: 'Gasoline',
    Status: 'Active',
    Department: 'Public Works',
    AssignedDriver: 'J. Doe',
    CurrentMileage: 42000,
    AcquisitionDate: '2019-06-01',
    AcquisitionCost: 35000,
    LicensePlate: 'PW-123',
    Location: 'Main Yard',
    Notes: null,
  }

  it('parses a canonical PascalCase payload into camelCase', () => {
    const parsed = VehicleSchema.parse(canonical)
    expect(parsed.assetNumber).toBe('PW-001')
    expect(parsed.currentMileage).toBe(42000)
    expect(parsed.notes).toBeNull()
  })

  it('rejects missing required fields', () => {
    const { Id: _omit, ...missing } = canonical
    expect(() => VehicleSchema.parse(missing)).toThrow()
  })

  it('defaults ABSENT optional fields to null, matching present-but-null', () => {
    // The wire may omit AssignedDriver/Notes entirely rather than sending
    // null; both shapes must land as null in the domain object.
    const { AssignedDriver: _driver, Notes: _notes, ...withoutOptionals } = canonical
    const parsed = VehicleSchema.parse(withoutOptionals)
    expect(parsed.assignedDriver).toBeNull()
    expect(parsed.notes).toBeNull()
  })

  it('rejects a wrong-typed field (string mileage)', () => {
    expect(() => VehicleSchema.parse({ ...canonical, CurrentMileage: '42000' })).toThrow()
  })
})

describe('WorkOrderSchema', () => {
  const openOrder = {
    Id: 41,
    WorkOrderNumber: 'WO-2026-00019',
    VehicleId: 1,
    Status: 'InProgress',
    Priority: 'Critical',
    Description: 'Hydraulic lift cylinder failure',
    RequestedDate: '2026-06-20T00:00:00',
  }

  it('defaults all five nullable fields when absent (open order)', () => {
    const parsed = WorkOrderSchema.parse(openOrder)
    expect(parsed.completedDate).toBeNull()
    expect(parsed.assignedTechnician).toBeNull()
    expect(parsed.laborHours).toBeNull()
    expect(parsed.totalCost).toBeNull()
    expect(parsed.notes).toBeNull()
  })

  it('carries money fields through as numbers (completed order)', () => {
    const parsed = WorkOrderSchema.parse({
      ...openOrder,
      Status: 'Completed',
      CompletedDate: '2026-06-22T00:00:00',
      LaborHours: 6.5,
      TotalCost: 1840.25,
    })
    expect(parsed.laborHours).toBe(6.5)
    expect(parsed.totalCost).toBe(1840.25)
  })
})

describe('MaintenanceScheduleItemSchema', () => {
  it('camelizes the flattened vehicle fields and defaults nullables', () => {
    const parsed = MaintenanceScheduleItemSchema.parse({
      Id: 11,
      VehicleId: 1,
      VehicleAssetNumber: 'PW-001',
      VehicleDescription: '2021 Ford F-150',
      MaintenanceType: 'OilChange',
      CurrentMileage: 42000,
    })
    expect(parsed.vehicleAssetNumber).toBe('PW-001')
    expect(parsed.nextDueDate).toBeNull()
    expect(parsed.nextDueMileage).toBeNull()
    expect(parsed.lastCompletedDate).toBeNull()
    expect(parsed.lastCompletedMileage).toBeNull()
  })
})

describe('MaintenanceRecordSchema', () => {
  it('keeps the work-order linkage nullable', () => {
    const base = {
      Id: 31,
      VehicleId: 1,
      MaintenanceType: 'OilChange',
      PerformedDate: '2026-01-05T00:00:00',
      MileageAtService: 36000,
      Description: 'Full synthetic oil change',
      Cost: 89.95,
      TechnicianName: 'M. Alvarez',
    }
    expect(MaintenanceRecordSchema.parse(base).workOrderId).toBeNull()
    expect(MaintenanceRecordSchema.parse({ ...base, WorkOrderId: 41 }).workOrderId).toBe(41)
  })
})

describe('FleetSummarySchema', () => {
  it('parses counts into a camelCase shape', () => {
    const parsed = FleetSummarySchema.parse({
      TotalVehicles: 35,
      ByStatus: { Active: 30, InMaintenance: 3, OutOfService: 2 },
      ByFuelType: { Gasoline: 20, Diesel: 10, Electric: 5 },
      ByDepartment: { 'Public Works': 15, Police: 10, Fire: 10 },
    })
    expect(parsed.totalVehicles).toBe(35)
    expect(parsed.byStatus.Active).toBe(30)
  })
})

describe('ChatResponseSchema', () => {
  it('parses the chat envelope', () => {
    const parsed = ChatResponseSchema.parse({
      Response: 'Found 35 vehicles.',
      ConversationId: 'abc-123',
      FunctionsUsed: ['get_fleet_summary'],
    })
    expect(parsed.conversationId).toBe('abc-123')
    expect(parsed.functionsUsed).toEqual(['get_fleet_summary'])
  })
})
