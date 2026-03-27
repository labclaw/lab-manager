import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import { CloudBrainChat } from '@/components/chat/CloudBrainChat'

describe('CloudBrainChat', () => {
  it('renders chat input when connected', () => {
    renderWithProviders(<CloudBrainChat connected={true} />)

    expect(screen.getByPlaceholderText('Ask Cloud Brain...')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Ask Cloud Brain...')).not.toBeDisabled()
  })

  it('renders chat input when disconnected (disabled)', () => {
    renderWithProviders(<CloudBrainChat connected={false} />)

    expect(screen.getByPlaceholderText('Ask Cloud Brain...')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Ask Cloud Brain...')).toBeDisabled()
  })

  it('renders quick action chips when no messages exist', () => {
    renderWithProviders(<CloudBrainChat connected={true} />)

    expect(screen.getByText('Search PubMed')).toBeInTheDocument()
    expect(screen.getByText('Protein Lookup')).toBeInTheDocument()
    expect(screen.getByText('Drug Info')).toBeInTheDocument()
    expect(screen.getByText('Experiment Design')).toBeInTheDocument()
    expect(screen.getByText('Write Methods')).toBeInTheDocument()
    expect(screen.getByText('Gene Analysis')).toBeInTheDocument()
  })

  it('populates input when quick action chip is clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<CloudBrainChat connected={true} />)

    await user.click(screen.getByText('Protein Lookup'))

    expect(screen.getByPlaceholderText('Ask Cloud Brain...')).toHaveValue(
      'Look up protein P04637 in UniProt',
    )
  })

  it('does not populate input when quick action is clicked while disconnected', async () => {
    renderWithProviders(<CloudBrainChat connected={false} />)

    const chip = screen.getByText('Protein Lookup')
    expect(chip).toBeDisabled()
  })
})
