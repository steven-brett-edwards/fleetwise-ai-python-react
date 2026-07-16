import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../testing/server'
import { getOverdueMaintenance, getUpcomingMaintenance } from './maintenance'

describe('getOverdueMaintenance', () => {
  it('camelizes schedule items, defaulting absent nullables to null', async () => {
    const items = await getOverdueMaintenance()

    expect(items).toHaveLength(2)
    expect(items[0]).toMatchObject({
      vehicleAssetNumber: 'PW-001',
      maintenanceType: 'OilChange',
      nextDueMileage: 41000,
    })
    expect(items[1].nextDueDate).toBeNull()
    expect(items[1].lastCompletedMileage).toBeNull()
  })
})

describe('getUpcomingMaintenance', () => {
  it('passes the days and miles window as query params', async () => {
    let requestedUrl = ''
    server.use(
      http.get('/api/maintenance/upcoming', ({ request }) => {
        requestedUrl = request.url
        return HttpResponse.json([])
      }),
    )

    await getUpcomingMaintenance(45, 7500)

    const url = new URL(requestedUrl)
    expect(url.searchParams.get('days')).toBe('45')
    expect(url.searchParams.get('miles')).toBe('7500')
  })

  it('defaults to the 30-day / 5000-mile window', async () => {
    let requestedUrl = ''
    server.use(
      http.get('/api/maintenance/upcoming', ({ request }) => {
        requestedUrl = request.url
        return HttpResponse.json([])
      }),
    )

    await getUpcomingMaintenance()

    const url = new URL(requestedUrl)
    expect(url.searchParams.get('days')).toBe('30')
    expect(url.searchParams.get('miles')).toBe('5000')
  })
})
