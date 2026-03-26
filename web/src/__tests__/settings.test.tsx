import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { renderWithProviders } from '@/test/utils'
import { SettingsPage } from '@/pages/SettingsPage'

describe('SettingsPage', () => {
  const onError = vi.fn()

  it('renders all section headings', async () => {
    renderWithProviders(<SettingsPage onError={onError} />, {
      initialEntries: ['/settings'],
    })

    expect(screen.getByText('Lab Profile')).toBeInTheDocument()
    expect(screen.getByText('User Account')).toBeInTheDocument()
    expect(screen.getByText('AI Configuration')).toBeInTheDocument()
    expect(screen.getByText('Notifications')).toBeInTheDocument()
    expect(screen.getByText('Data Management')).toBeInTheDocument()
    expect(screen.getByText('System Info')).toBeInTheDocument()
    expect(screen.getByText('Danger Zone')).toBeInTheDocument()
  })

  it('renders lab profile fields', () => {
    renderWithProviders(<SettingsPage onError={onError} />, {
      initialEntries: ['/settings'],
    })

    expect(screen.getByLabelText('Lab Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Subtitle / Department')).toBeInTheDocument()
    expect(screen.getByLabelText('Institution')).toBeInTheDocument()
    expect(screen.getByLabelText('PI Name')).toBeInTheDocument()
  })

  it('renders AI configuration cards', () => {
    renderWithProviders(<SettingsPage onError={onError} />, {
      initialEntries: ['/settings'],
    })

    expect(screen.getByText('OCR Model')).toBeInTheDocument()
    expect(screen.getByText('Extraction Model')).toBeInTheDocument()
    expect(screen.getByText('RAG Model')).toBeInTheDocument()
  })

  it('renders notification toggles', () => {
    renderWithProviders(<SettingsPage onError={onError} />, {
      initialEntries: ['/settings'],
    })

    expect(screen.getByText('Email notifications')).toBeInTheDocument()
    expect(screen.getByText('Low stock alerts')).toBeInTheDocument()
    expect(screen.getByText('Expiring reagents alerts')).toBeInTheDocument()
    expect(screen.getByText('New document processed')).toBeInTheDocument()
  })

  it('renders data export links', () => {
    renderWithProviders(<SettingsPage onError={onError} />, {
      initialEntries: ['/settings'],
    })

    expect(screen.getByText('Export Inventory (CSV)')).toBeInTheDocument()
    expect(screen.getByText('Export Orders (CSV)')).toBeInTheDocument()
    expect(screen.getByText('Export Products (CSV)')).toBeInTheDocument()
    expect(screen.getByText('Export Vendors (CSV)')).toBeInTheDocument()
  })

  it('renders system info section with version and stats', async () => {
    renderWithProviders(<SettingsPage onError={onError} />, {
      initialEntries: ['/settings'],
    })

    expect(screen.getByText('Version')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Total Documents')).toBeInTheDocument()
      expect(screen.getByText('Approved')).toBeInTheDocument()
    })
  })

  it('shows Coming Soon badges for disabled features', () => {
    renderWithProviders(<SettingsPage onError={onError} />, {
      initialEntries: ['/settings'],
    })

    const comingSoonBadges = screen.getAllByText('Coming Soon')
    expect(comingSoonBadges.length).toBeGreaterThanOrEqual(3)
  })

  it('loads config data from API and displays version', async () => {
    renderWithProviders(<SettingsPage onError={onError} />, {
      initialEntries: ['/settings'],
    })

    await waitFor(() => {
      expect(screen.getByText('v0.1.10')).toBeInTheDocument()
    })
  })

  it('loads config data and displays lab name', async () => {
    renderWithProviders(<SettingsPage onError={onError} />, {
      initialEntries: ['/settings'],
    })

    await waitFor(() => {
      const labNameInput = screen.getByLabelText('Lab Name') as HTMLInputElement
      expect(labNameInput.value).toBe('Research Lab')
    })
  })

  it('loads user data and displays user name', async () => {
    renderWithProviders(<SettingsPage onError={onError} />, {
      initialEntries: ['/settings'],
    })

    await waitFor(() => {
      expect(screen.getByText('Dr. Aris Thorne')).toBeInTheDocument()
      expect(screen.getByText('aris@example.com')).toBeInTheDocument()
      expect(screen.getByText('admin')).toBeInTheDocument()
    })
  })

  it('loads dashboard stats in about section', async () => {
    renderWithProviders(<SettingsPage onError={onError} />, {
      initialEntries: ['/settings'],
    })

    await waitFor(() => {
      expect(screen.getByText('Total Documents')).toBeInTheDocument()
      expect(screen.getByText('Total Vendors')).toBeInTheDocument()
    })
  })

  it('renders change password section as disabled', () => {
    renderWithProviders(<SettingsPage onError={onError} />, {
      initialEntries: ['/settings'],
    })

    expect(screen.getByText('Change Password')).toBeInTheDocument()
    expect(screen.getByLabelText('Current Password')).toBeDisabled()
    expect(screen.getByLabelText('New Password')).toBeDisabled()
    expect(screen.getByLabelText('Confirm Password')).toBeDisabled()
  })

  it('renders confidence threshold slider', () => {
    renderWithProviders(<SettingsPage onError={onError} />, {
      initialEntries: ['/settings'],
    })

    expect(screen.getByText('Confidence threshold for auto-approve')).toBeInTheDocument()
    expect(screen.getByText('0.95')).toBeInTheDocument()
  })

  it('all lab profile fields are disabled', () => {
    renderWithProviders(<SettingsPage onError={onError} />, {
      initialEntries: ['/settings'],
    })

    expect(screen.getByLabelText('Lab Name')).toBeDisabled()
    expect(screen.getByLabelText('Subtitle / Department')).toBeDisabled()
    expect(screen.getByLabelText('Institution')).toBeDisabled()
    expect(screen.getByLabelText('PI Name')).toBeDisabled()
  })

  it('renders AI configuration as read-only cards', async () => {
    renderWithProviders(<SettingsPage onError={onError} />, {
      initialEntries: ['/settings'],
    })

    await waitFor(() => {
      expect(screen.getByText('Llama 3.2 90B Vision')).toBeInTheDocument()
      expect(screen.getByText('GLM-5')).toBeInTheDocument()
      expect(screen.getByText('GLM-5 Turbo')).toBeInTheDocument()
      expect(screen.getByText('AUTO')).toBeInTheDocument()
    })
  })
})
