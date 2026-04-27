import { z } from 'zod'

// Wire is PascalCase (FastAPI Pydantic alias_generator=to_pascal). We parse
// with PascalCase schemas, then `.transform()` into camelCase domain objects
// so internal React code stays idiomatic.

export const VehicleSchema = z
  .object({
    Id: z.number(),
    AssetNumber: z.string(),
    Vin: z.string(),
    Year: z.number(),
    Make: z.string(),
    Model: z.string(),
    FuelType: z.string(),
    Status: z.string(),
    Department: z.string(),
    AssignedDriver: z.string().nullable().optional(),
    CurrentMileage: z.number(),
    AcquisitionDate: z.string(),
    AcquisitionCost: z.number(),
    LicensePlate: z.string(),
    Location: z.string(),
    Notes: z.string().nullable().optional(),
  })
  .transform((v) => ({
    id: v.Id,
    assetNumber: v.AssetNumber,
    vin: v.Vin,
    year: v.Year,
    make: v.Make,
    model: v.Model,
    fuelType: v.FuelType,
    status: v.Status,
    department: v.Department,
    assignedDriver: v.AssignedDriver ?? null,
    currentMileage: v.CurrentMileage,
    acquisitionDate: v.AcquisitionDate,
    acquisitionCost: v.AcquisitionCost,
    licensePlate: v.LicensePlate,
    location: v.Location,
    notes: v.Notes ?? null,
  }))
export type Vehicle = z.infer<typeof VehicleSchema>

export const FleetSummarySchema = z
  .object({
    TotalVehicles: z.number(),
    ByStatus: z.record(z.string(), z.number()),
    ByFuelType: z.record(z.string(), z.number()),
    ByDepartment: z.record(z.string(), z.number()),
  })
  .transform((v) => ({
    totalVehicles: v.TotalVehicles,
    byStatus: v.ByStatus,
    byFuelType: v.ByFuelType,
    byDepartment: v.ByDepartment,
  }))
export type FleetSummary = z.infer<typeof FleetSummarySchema>

export const MaintenanceScheduleItemSchema = z
  .object({
    Id: z.number(),
    VehicleId: z.number(),
    VehicleAssetNumber: z.string(),
    VehicleDescription: z.string(),
    MaintenanceType: z.string(),
    NextDueDate: z.string().nullable().optional(),
    NextDueMileage: z.number().nullable().optional(),
    CurrentMileage: z.number(),
    LastCompletedDate: z.string().nullable().optional(),
    LastCompletedMileage: z.number().nullable().optional(),
  })
  .transform((v) => ({
    id: v.Id,
    vehicleId: v.VehicleId,
    vehicleAssetNumber: v.VehicleAssetNumber,
    vehicleDescription: v.VehicleDescription,
    maintenanceType: v.MaintenanceType,
    nextDueDate: v.NextDueDate ?? null,
    nextDueMileage: v.NextDueMileage ?? null,
    currentMileage: v.CurrentMileage,
    lastCompletedDate: v.LastCompletedDate ?? null,
    lastCompletedMileage: v.LastCompletedMileage ?? null,
  }))
export type MaintenanceScheduleItem = z.infer<typeof MaintenanceScheduleItemSchema>

export const MaintenanceRecordSchema = z
  .object({
    Id: z.number(),
    VehicleId: z.number(),
    WorkOrderId: z.number().nullable().optional(),
    MaintenanceType: z.string(),
    PerformedDate: z.string(),
    MileageAtService: z.number(),
    Description: z.string(),
    Cost: z.number(),
    TechnicianName: z.string(),
  })
  .transform((v) => ({
    id: v.Id,
    vehicleId: v.VehicleId,
    workOrderId: v.WorkOrderId ?? null,
    maintenanceType: v.MaintenanceType,
    performedDate: v.PerformedDate,
    mileageAtService: v.MileageAtService,
    description: v.Description,
    cost: v.Cost,
    technicianName: v.TechnicianName,
  }))
export type MaintenanceRecord = z.infer<typeof MaintenanceRecordSchema>

export const WorkOrderSchema = z
  .object({
    Id: z.number(),
    WorkOrderNumber: z.string(),
    VehicleId: z.number(),
    Status: z.string(),
    Priority: z.string(),
    Description: z.string(),
    RequestedDate: z.string(),
    CompletedDate: z.string().nullable().optional(),
    AssignedTechnician: z.string().nullable().optional(),
    LaborHours: z.number().nullable().optional(),
    TotalCost: z.number().nullable().optional(),
    Notes: z.string().nullable().optional(),
  })
  .transform((v) => ({
    id: v.Id,
    workOrderNumber: v.WorkOrderNumber,
    vehicleId: v.VehicleId,
    status: v.Status,
    priority: v.Priority,
    description: v.Description,
    requestedDate: v.RequestedDate,
    completedDate: v.CompletedDate ?? null,
    assignedTechnician: v.AssignedTechnician ?? null,
    laborHours: v.LaborHours ?? null,
    totalCost: v.TotalCost ?? null,
    notes: v.Notes ?? null,
  }))
export type WorkOrder = z.infer<typeof WorkOrderSchema>

export const ChatResponseSchema = z
  .object({
    Response: z.string(),
    ConversationId: z.string(),
    FunctionsUsed: z.array(z.string()),
  })
  .transform((v) => ({
    response: v.Response,
    conversationId: v.ConversationId,
    functionsUsed: v.FunctionsUsed,
  }))
export type ChatResponse = z.infer<typeof ChatResponseSchema>
