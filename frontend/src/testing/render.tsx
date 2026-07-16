import type { ReactElement, ReactNode } from 'react'
import { render, type RenderResult } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// Route-aware render with the same provider stack main.tsx mounts, minus
// BrowserRouter (MemoryRouter lets each test pick its starting URL).
// A fresh QueryClient per render keeps tests hermetic; retries are off so
// error-path tests fail fast instead of exhausting three retries.

interface RenderRouteOptions {
  /** Route pattern the component is mounted at, e.g. `/vehicles/:id`. */
  path?: string
  /** Initial URL, e.g. `/vehicles/1?status=Active`. */
  route?: string
  /** Extra routes rendered alongside (link-navigation targets). */
  extraRoutes?: ReactNode
}

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  })
}

export function renderRoute(
  ui: ReactElement,
  { path = '/', route = '/', extraRoutes }: RenderRouteOptions = {},
): RenderResult {
  return render(
    <QueryClientProvider client={makeQueryClient()}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path={path} element={ui} />
          {extraRoutes}
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
