import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import { renderWithProviders } from '@/test/utils'
import { CloudBrainPage } from '@/pages/CloudBrainPage'

// Helper to mock Cloud Brain as offline (network error)
function mockBrainOffline() {
  server.use(
    http.get('/brain/health', () => HttpResponse.error()),
  )
}

// Helper to mock Cloud Brain as online with health data
function mockBrainOnline(overrides?: Record<string, unknown>) {
  const healthData = {
    status: 'ok',
    skills: { tooluniverse: true, lifesci: true, write: true },
    tool_count: 2400,
    version: '0.0.1',
    ...overrides,
  }
  server.use(
    http.get('/brain/health', () => HttpResponse.json(healthData)),
  )
}

describe('CloudBrainPage', () => {
  const onError = vi.fn()

  beforeEach(() => {
    onError.mockClear()
  })

  it('renders the Cloud Brain heading and description', () => {
    mockBrainOffline()

    renderWithProviders(<CloudBrainPage onError={onError} />, {
      initialEntries: ['/cloud-brain'],
    })

    expect(screen.getByText('Cloud Brain')).toBeInTheDocument()
    expect(screen.getByText('Unified scientific AI gateway')).toBeInTheDocument()
  })

  it('renders all six skill cards', () => {
    mockBrainOffline()

    renderWithProviders(<CloudBrainPage onError={onError} />, {
      initialEntries: ['/cloud-brain'],
    })

    expect(screen.getByText('ToolUniverse')).toBeInTheDocument()
    expect(screen.getByText('K-Dense AI')).toBeInTheDocument()
    expect(screen.getByText('Biomni')).toBeInTheDocument()
    expect(screen.getByText('Life Science Reasoning')).toBeInTheDocument()
    expect(screen.getByText('LifeSci MCP')).toBeInTheDocument()
    expect(screen.getByText('Scientific Writing')).toBeInTheDocument()
  })

  it('renders quick action buttons', () => {
    mockBrainOffline()

    renderWithProviders(<CloudBrainPage onError={onError} />, {
      initialEntries: ['/cloud-brain'],
    })

    expect(screen.getByText('Search PubMed')).toBeInTheDocument()
    expect(screen.getByText('Protein Lookup')).toBeInTheDocument()
    expect(screen.getByText('Drug Info')).toBeInTheDocument()
    expect(screen.getByText('Gene Analysis')).toBeInTheDocument()
    // "Experiment Design" and "Write Section" also appear as category tags,
    // so just verify we have 6 quick-action buttons total
    const heading = screen.getByText('Quick Actions')
    const section = heading.closest('div')!
    const buttons = within(section).getAllByRole('button')
    expect(buttons.length).toBe(6)
  })

  it('shows not connected status when Cloud Brain is offline', async () => {
    mockBrainOffline()

    renderWithProviders(<CloudBrainPage onError={onError} />, {
      initialEntries: ['/cloud-brain'],
    })

    expect(await screen.findByText('Not Connected')).toBeInTheDocument()
  })

  it('shows offline notice with labclaw command when not connected', async () => {
    mockBrainOffline()

    renderWithProviders(<CloudBrainPage onError={onError} />, {
      initialEntries: ['/cloud-brain'],
    })

    expect(await screen.findByText('Cloud Brain is not running')).toBeInTheDocument()
    expect(screen.getByText('labclaw brain --port 18802')).toBeInTheDocument()
  })

  it('shows connected status when Cloud Brain is running', async () => {
    mockBrainOnline()

    renderWithProviders(<CloudBrainPage onError={onError} />, {
      initialEntries: ['/cloud-brain'],
    })

    await waitFor(() => {
      expect(screen.getByText(/Connected.*2,?400 tools/)).toBeInTheDocument()
    })
  })

  it('shows stats row when connected', async () => {
    mockBrainOnline()

    renderWithProviders(<CloudBrainPage onError={onError} />, {
      initialEntries: ['/cloud-brain'],
    })

    await waitFor(() => {
      expect(screen.getByText('Tools Available')).toBeInTheDocument()
      expect(screen.getByText('Active Skills')).toBeInTheDocument()
      expect(screen.getByText('Skills Healthy')).toBeInTheDocument()
      expect(screen.getByText('Version')).toBeInTheDocument()
    })
  })

  it('shows query input when connected', async () => {
    mockBrainOnline({ tool_count: 100 })

    renderWithProviders(<CloudBrainPage onError={onError} />, {
      initialEntries: ['/cloud-brain'],
    })

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText('Ask Cloud Brain a scientific question...'),
      ).toBeInTheDocument()
    })
  })

  it('does not show query input when offline', async () => {
    mockBrainOffline()

    renderWithProviders(<CloudBrainPage onError={onError} />, {
      initialEntries: ['/cloud-brain'],
    })

    expect(await screen.findByText('Not Connected')).toBeInTheDocument()
    expect(
      screen.queryByPlaceholderText('Ask Cloud Brain a scientific question...'),
    ).not.toBeInTheDocument()
  })

  it('renders API reference section', () => {
    mockBrainOffline()

    renderWithProviders(<CloudBrainPage onError={onError} />, {
      initialEntries: ['/cloud-brain'],
    })

    expect(screen.getByText('POST /brain/execute')).toBeInTheDocument()
    expect(screen.getByText('POST /brain/reason')).toBeInTheDocument()
    expect(screen.getByText('POST /brain/write')).toBeInTheDocument()
    expect(screen.getByText('GET /brain/tools')).toBeInTheDocument()
  })

  it('renders total tool count in the description', () => {
    mockBrainOffline()

    renderWithProviders(<CloudBrainPage onError={onError} />, {
      initialEntries: ['/cloud-brain'],
    })

    // The count appears in both the hero description and footer summary
    const matches = screen.getAllByText(/2,453\+/)
    expect(matches.length).toBeGreaterThanOrEqual(1)
  })

  it('shows skill categories on a card', () => {
    mockBrainOffline()

    renderWithProviders(<CloudBrainPage onError={onError} />, {
      initialEntries: ['/cloud-brain'],
    })

    expect(screen.getByText('Genomics')).toBeInTheDocument()
    expect(screen.getByText('Drug Discovery')).toBeInTheDocument()
  })

  it('shows source link for ToolUniverse', () => {
    mockBrainOffline()

    renderWithProviders(<CloudBrainPage onError={onError} />, {
      initialEntries: ['/cloud-brain'],
    })

    const tuLink = screen.getByText('mims-harvard/ToolUniverse')
    expect(tuLink.closest('a')).toHaveAttribute(
      'href',
      'https://github.com/mims-harvard/ToolUniverse',
    )
  })

  it('expands skill card to show examples on click', async () => {
    mockBrainOffline()
    const user = userEvent.setup()

    renderWithProviders(<CloudBrainPage onError={onError} />, {
      initialEntries: ['/cloud-brain'],
    })

    // Wait for component to settle (fetch rejection resolves)
    await screen.findByText('Not Connected')

    // Initially no example text visible
    expect(
      screen.queryByText('Look up protein P04637 in UniProt'),
    ).not.toBeInTheDocument()

    // Click first "Try examples" button
    const buttons = screen.getAllByText('Try examples')
    await user.click(buttons[0])

    // Now example is visible
    expect(
      screen.getByText('Look up protein P04637 in UniProt'),
    ).toBeInTheDocument()
  })

  it('displays tool count per skill card', () => {
    mockBrainOffline()

    renderWithProviders(<CloudBrainPage onError={onError} />, {
      initialEntries: ['/cloud-brain'],
    })

    expect(screen.getByText('2,124 tools')).toBeInTheDocument()
    expect(screen.getByText('170 tools')).toBeInTheDocument()
    expect(screen.getByText('150 tools')).toBeInTheDocument()
  })
})
