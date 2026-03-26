import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import { ConfidenceBadge } from '@/components/ui/ConfidenceBadge'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorBanner } from '@/components/ui/ErrorBanner'
import { SkeletonTable } from '@/components/ui/SkeletonTable'
import { Sidebar } from '@/components/layout/Sidebar'

describe('ConfidenceBadge', () => {
  it('shows "High" with green color for confidence >= 0.95', () => {
    renderWithProviders(<ConfidenceBadge confidence={0.97} />)
    const badge = screen.getByText('High (97%)')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveStyle({ color: '#00D4AA' })
  })

  it('shows "Medium" with purple color for confidence 0.80-0.94', () => {
    renderWithProviders(<ConfidenceBadge confidence={0.85} />)
    const badge = screen.getByText('Medium (85%)')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveStyle({ color: '#6C5CE7' })
  })

  it('shows "Low" with yellow/orange color for confidence 0.50-0.79', () => {
    renderWithProviders(<ConfidenceBadge confidence={0.65} />)
    const badge = screen.getByText('Low (65%)')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveStyle({ color: '#F39C12' })
  })

  it('shows "Needs Review" with red color for confidence < 0.50', () => {
    renderWithProviders(<ConfidenceBadge confidence={0.30} />)
    const badge = screen.getByText('Needs Review (30%)')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveStyle({ color: '#E74C3C' })
  })

  it('shows dash for null confidence', () => {
    renderWithProviders(<ConfidenceBadge confidence={null} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('shows dash for undefined confidence', () => {
    renderWithProviders(<ConfidenceBadge confidence={undefined} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })
})

describe('EmptyState', () => {
  it('renders title', () => {
    renderWithProviders(<EmptyState title="No documents found" />)
    expect(screen.getByText('No documents found')).toBeInTheDocument()
  })

  it('renders description when provided', () => {
    renderWithProviders(
      <EmptyState title="No results" description="Try adjusting your search" />,
    )
    expect(screen.getByText('Try adjusting your search')).toBeInTheDocument()
  })

  it('does not render description when not provided', () => {
    renderWithProviders(<EmptyState title="Empty" />)
    expect(screen.queryByText('Try adjusting')).not.toBeInTheDocument()
  })

  it('renders action button when provided', () => {
    renderWithProviders(
      <EmptyState
        title="No items"
        action={<button>Add Item</button>}
      />,
    )
    expect(screen.getByText('Add Item')).toBeInTheDocument()
  })
})

describe('ErrorBanner', () => {
  it('renders error message', () => {
    renderWithProviders(<ErrorBanner error="Something went wrong" onDismiss={() => {}} />)
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })

  it('returns null when error is null', () => {
    const { container } = renderWithProviders(
      <ErrorBanner error={null} onDismiss={() => {}} />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('dismiss button calls onDismiss', async () => {
    const onDismiss = vi.fn()
    renderWithProviders(<ErrorBanner error="Error occurred" onDismiss={onDismiss} />)
    const dismissButton = screen.getByRole('button', { name: 'Dismiss' })
    await userEvent.click(dismissButton)
    expect(onDismiss).toHaveBeenCalledOnce()
  })
})

describe('SkeletonTable', () => {
  it('renders default 5 rows and 4 columns', () => {
    renderWithProviders(<SkeletonTable />)
    const table = screen.getByRole('table')
    const headerCells = table.querySelectorAll('thead th')
    const bodyRows = table.querySelectorAll('tbody tr')
    const bodyCells = table.querySelectorAll('tbody td')
    expect(headerCells).toHaveLength(4)
    expect(bodyRows).toHaveLength(5)
    expect(bodyCells).toHaveLength(20) // 5 rows * 4 cols
  })

  it('renders custom row and column count', () => {
    renderWithProviders(<SkeletonTable rows={3} columns={6} />)
    const table = screen.getByRole('table')
    const headerCells = table.querySelectorAll('thead th')
    const bodyRows = table.querySelectorAll('tbody tr')
    const bodyCells = table.querySelectorAll('tbody td')
    expect(headerCells).toHaveLength(6)
    expect(bodyRows).toHaveLength(3)
    expect(bodyCells).toHaveLength(18) // 3 rows * 6 cols
  })
})

describe('Sidebar', () => {
  const defaultProps = {
    current: '/',
    collapsed: false,
    onToggle: vi.fn(),
  }

  it('renders all nav links', () => {
    renderWithProviders(<Sidebar {...defaultProps} />)
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Documents')).toBeInTheDocument()
    expect(screen.getByText('Review Queue')).toBeInTheDocument()
    expect(screen.getByText('Inventory')).toBeInTheDocument()
    expect(screen.getByText('Orders')).toBeInTheDocument()
    expect(screen.getByText('Upload')).toBeInTheDocument()
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })

  it('highlights the current route', () => {
    renderWithProviders(<Sidebar {...defaultProps} current="/documents" />)
    const docsLink = screen.getByText('Documents').closest('a')!
    expect(docsLink.className).toContain('bg-primary/10')
    expect(docsLink.className).toContain('font-semibold')

    const dashboardLink = screen.getByText('Dashboard').closest('a')!
    expect(dashboardLink.className).not.toContain('bg-primary/10')
  })

  it('shows review badge count when reviewCount > 0', () => {
    renderWithProviders(<Sidebar {...defaultProps} reviewCount={7} />)
    expect(screen.getByText('7')).toBeInTheDocument()
  })

  it('does not show badge when count is 0', () => {
    renderWithProviders(<Sidebar {...defaultProps} reviewCount={0} />)
    // No badge numbers should be rendered
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('highlights settings link when on /settings', () => {
    renderWithProviders(<Sidebar {...defaultProps} current="/settings" />)
    const settingsLink = screen.getByText('Settings').closest('a')!
    expect(settingsLink.className).toContain('bg-primary/10')
    expect(settingsLink.className).toContain('font-semibold')
  })

  it('hides labels when collapsed', () => {
    renderWithProviders(<Sidebar {...defaultProps} collapsed={true} />)
    expect(screen.queryByText('Dashboard')).not.toBeInTheDocument()
    expect(screen.queryByText('Documents')).not.toBeInTheDocument()
  })

  it('shows provided userName instead of hardcoded Admin', () => {
    renderWithProviders(<Sidebar {...defaultProps} userName="Dr. Aris Thorne" />)
    expect(screen.getByText('Dr. Aris Thorne')).toBeInTheDocument()
    expect(screen.queryByText('Admin')).not.toBeInTheDocument()
  })

  it('defaults to "User" when userName is not provided', () => {
    renderWithProviders(<Sidebar {...defaultProps} />)
    expect(screen.getByText('User')).toBeInTheDocument()
  })
})
