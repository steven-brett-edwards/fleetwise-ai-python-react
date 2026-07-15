import { describe, expect, it } from 'vitest'
import { getWorkOrderById, getWorkOrders } from './workOrders'
import { ApiError } from './client'

describe('getWorkOrders', () => {
  it('returns all camelized work orders with no filter', async () => {
    const orders = await getWorkOrders()

    expect(orders).toHaveLength(2)
    expect(orders[0]).toMatchObject({
      workOrderNumber: 'WO-2026-00019',
      priority: 'Critical',
      totalCost: null,
    })
  })

  it('filters by status on the wire', async () => {
    const orders = await getWorkOrders({ status: 'Completed' })

    expect(orders).toHaveLength(1)
    expect(orders[0].workOrderNumber).toBe('WO-2026-00023')
  })
})

describe('getWorkOrderById', () => {
  it('returns one work order with nullables defaulted', async () => {
    const wo = await getWorkOrderById(42)

    expect(wo.completedDate).toBe('2026-05-04T00:00:00')
    expect(wo.assignedTechnician).toBeNull()
    expect(wo.laborHours).toBe(2.5)
    expect(wo.notes).toBeNull()
  })

  it('rejects with ApiError on 404', async () => {
    await expect(getWorkOrderById(999)).rejects.toBeInstanceOf(ApiError)
  })
})
