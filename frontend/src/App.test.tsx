import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { ChatProvider } from './contexts/ChatContext'
import Dashboard from './routes/Dashboard'
import Vehicles from './routes/Vehicles'
import VehicleDetail from './routes/VehicleDetail'
import WorkOrders from './routes/WorkOrders'
import WorkOrderDetail from './routes/WorkOrderDetail'
import Chat from './routes/Chat'
import { makeQueryClient } from './testing/render'

// The chat route pulls in streamChat; a no-op mock keeps this a routing test.
vi.mock('./api/chat', () => ({ streamChat: vi.fn().mockResolvedValue(null) }))

// Mirrors the route tree main.tsx mounts (main.tsx itself is bootstrap-only
// and excluded from coverage; the wiring is what's worth pinning).
function renderAppAt(route: string) {
  return render(
    <QueryClientProvider client={makeQueryClient()}>
      <ChatProvider>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route element={<App />}>
              <Route index element={<Dashboard />} />
              <Route path="vehicles" element={<Vehicles />} />
              <Route path="vehicles/:id" element={<VehicleDetail />} />
              <Route path="work-orders" element={<WorkOrders />} />
              <Route path="work-orders/:id" element={<WorkOrderDetail />} />
              <Route path="chat" element={<Chat />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </ChatProvider>
    </QueryClientProvider>,
  )
}

describe('App shell routing', () => {
  it.each([
    ['/', 'Fleet Dashboard'],
    ['/vehicles', 'Vehicles'],
    ['/vehicles/1', '2021 Ford F-150'],
    ['/work-orders', 'Work orders'],
    ['/work-orders/41', 'Hydraulic lift cylinder failure'],
    ['/chat', 'Chat with the fleet'],
  ])('renders the sidenav plus the %s route', async (route, headingText) => {
    renderAppAt(route)

    // Shell is always present…
    expect(screen.getByText('FleetWise')).toBeInTheDocument()
    // …and the routed page renders its h1 (role query dodges the sidenav
    // links that share text like "Vehicles" / "Work orders").
    expect(await screen.findByRole('heading', { name: headingText })).toBeInTheDocument()
  })
})
