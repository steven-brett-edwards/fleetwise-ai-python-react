import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { QueryClientProvider } from '@tanstack/react-query'
import { server } from '../testing/server'
import { makeQueryClient } from '../testing/render'
import {
  useFleetSummary,
  useVehicle,
  useVehicles,
  useWorkOrder,
} from './useFleetData'

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={makeQueryClient()}>{children}</QueryClientProvider>
}

describe('useFleetSummary', () => {
  it('resolves the camelized summary', async () => {
    const { result } = renderHook(() => useFleetSummary(), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.totalVehicles).toBe(35)
  })
})

describe('useVehicles', () => {
  it('keys the query on the filters so filter changes refetch', async () => {
    const { result, rerender } = renderHook(
      ({ status }: { status?: string }) => useVehicles({ status }),
      { wrapper, initialProps: {} },
    )
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toHaveLength(3)

    rerender({ status: 'InShop' })
    await waitFor(() => expect(result.current.data).toHaveLength(1))
    expect(result.current.data?.[0].assetNumber).toBe('PK-014')
  })

  it('surfaces a server failure as isError', async () => {
    server.use(http.get('/api/vehicles', () => new HttpResponse(null, { status: 500 })))

    const { result } = renderHook(() => useVehicles({}), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

describe('useVehicle', () => {
  it('does not fetch until it has a real id', async () => {
    const { result } = renderHook(() => useVehicle(null), { wrapper })

    // enabled: false leaves the query idle -- no request, no data.
    expect(result.current.fetchStatus).toBe('idle')
    expect(result.current.data).toBeUndefined()
  })

  it('fetches once the id is set', async () => {
    const { result } = renderHook(() => useVehicle(3), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.assetNumber).toBe('SN-030')
  })
})

describe('useWorkOrder', () => {
  it('stays idle for a null id and resolves for a real one', async () => {
    const idle = renderHook(() => useWorkOrder(null), { wrapper })
    expect(idle.result.current.fetchStatus).toBe('idle')

    const live = renderHook(() => useWorkOrder(41), { wrapper })
    await waitFor(() => expect(live.result.current.isSuccess).toBe(true))
    expect(live.result.current.data?.workOrderNumber).toBe('WO-2026-00019')
  })
})
