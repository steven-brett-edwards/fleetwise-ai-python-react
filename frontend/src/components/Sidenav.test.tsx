import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import Sidenav from './Sidenav'

function renderAt(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Sidenav />
    </MemoryRouter>,
  )
}

describe('Sidenav', () => {
  it('renders all four nav links with their targets', () => {
    renderAt('/')

    expect(screen.getByRole('link', { name: /dashboard/i })).toHaveAttribute('href', '/')
    expect(screen.getByRole('link', { name: /vehicles/i })).toHaveAttribute('href', '/vehicles')
    expect(screen.getByRole('link', { name: /work orders/i })).toHaveAttribute(
      'href',
      '/work-orders',
    )
    expect(screen.getByRole('link', { name: /chat/i })).toHaveAttribute('href', '/chat')
  })

  it('marks only the current route active (aria-current)', () => {
    renderAt('/vehicles')

    expect(screen.getByRole('link', { name: /vehicles/i })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(screen.getByRole('link', { name: /dashboard/i })).not.toHaveAttribute('aria-current')
  })

  it('the dashboard link is exact: it is not active on child routes', () => {
    renderAt('/work-orders')

    expect(screen.getByRole('link', { name: /dashboard/i })).not.toHaveAttribute('aria-current')
    expect(screen.getByRole('link', { name: /work orders/i })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })
})
