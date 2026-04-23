import { describe, expect, it } from 'vitest'
import {
  ChatResponseSchema,
  FleetSummarySchema,
  VehicleSchema,
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
