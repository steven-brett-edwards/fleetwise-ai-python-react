import { z } from 'zod'
import { apiGet } from './client'
import { WorkOrderSchema, type WorkOrder } from './schemas'

export interface WorkOrderFilters {
  status?: string
}

function toQuery(filters?: WorkOrderFilters): string {
  if (!filters?.status) return ''
  const params = new URLSearchParams()
  params.set('status', filters.status)
  return `?${params.toString()}`
}

export function getWorkOrders(filters?: WorkOrderFilters): Promise<WorkOrder[]> {
  return apiGet(`/work-orders${toQuery(filters)}`, (raw) =>
    z.array(WorkOrderSchema).parse(raw),
  )
}

export function getWorkOrderById(id: number): Promise<WorkOrder> {
  return apiGet(`/work-orders/${id}`, (raw) => WorkOrderSchema.parse(raw))
}
