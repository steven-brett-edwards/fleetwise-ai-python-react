import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import Markdown from './Markdown'

describe('Markdown', () => {
  it('renders a GFM table with headers and cells', () => {
    render(
      <Markdown source={'| Asset | Status |\n|---|---|\n| PW-001 | Active |'} />,
    )

    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Asset' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'PW-001' })).toBeInTheDocument()
  })

  it('renders lists, bold, and inline code', () => {
    render(<Markdown source={'- item **one** with `code`\n- item two'} />)

    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByText('one').tagName).toBe('STRONG')
    expect(screen.getByText('code').tagName).toBe('CODE')
  })

  it('opens links in a new tab with rel protection', () => {
    render(<Markdown source={'[the SOP](https://example.com/sop)'} />)

    const link = screen.getByRole('link', { name: 'the SOP' })
    expect(link).toHaveAttribute('href', 'https://example.com/sop')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('renders fenced code blocks inside a pre', () => {
    render(<Markdown source={'```\nSELECT 1;\n```'} />)

    const code = screen.getByText('SELECT 1;')
    expect(code.closest('pre')).not.toBeNull()
  })

  it('renders headings and blockquotes', () => {
    render(<Markdown source={'## Policy\n\n> Idle limit is 3 minutes.'} />)

    expect(screen.getByRole('heading', { level: 2, name: 'Policy' })).toBeInTheDocument()
    expect(screen.getByText('Idle limit is 3 minutes.')).toBeInTheDocument()
  })

  it('renders h1 and h3 headings', () => {
    render(<Markdown source={'# Top\n\n### Sub'} />)

    expect(screen.getByRole('heading', { level: 1, name: 'Top' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 3, name: 'Sub' })).toBeInTheDocument()
  })

  it('renders emphasis, ordered lists, and horizontal rules', () => {
    const { container } = render(<Markdown source={'*note*\n\n1. first\n2. second\n\n---'} />)

    expect(screen.getByText('note').tagName).toBe('EM')
    expect(container.querySelector('ol')).not.toBeNull()
    expect(container.querySelector('hr')).not.toBeNull()
  })
})
