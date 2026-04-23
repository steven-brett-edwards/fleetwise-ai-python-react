import { z } from 'zod'
import { apiGet } from './client'
import { MaintenanceScheduleItemSchema, type MaintenanceScheduleItem } from './schemas'

export function getOverdueMaintenance(): Promise<MaintenanceScheduleItem[]> {
  return apiGet('/maintenance/overdue', (raw) =>
    z.array(MaintenanceScheduleItemSchema).parse(raw),
  )
}

export function getUpcomingMaintenance(days = 30, miles = 5000): Promise<MaintenanceScheduleItem[]> {
  return apiGet(`/maintenance/upcoming?days=${days}&miles=${miles}`, (raw) =>
    z.array(MaintenanceScheduleItemSchema).parse(raw),
  )
}
