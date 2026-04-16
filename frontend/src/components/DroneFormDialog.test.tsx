import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DroneFormDialog } from './DroneFormDialog'
import type { Drone } from '../types'

const mockDrone: Drone = {
  id: 1,
  name: 'Test Drone',
  description: 'A test description',
  frame_size: '5-inch',
  motor_kv: 2400,
  prop_size: '5.1x3.6x3',
  weight_g: 280,
  notes: 'Some notes',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-02T00:00:00Z',
}

describe('DroneFormDialog', () => {
  describe('when open is false', () => {
    it('renders nothing when closed', () => {
      const { container } = render(
        <DroneFormDialog
          open={false}
          onClose={vi.fn()}
          onSubmit={vi.fn()}
        />,
      )
      expect(container).toBeEmptyDOMElement()
    })
  })

  describe('when open is true', () => {
    it('renders the dialog when open', () => {
      render(
        <DroneFormDialog
          open={true}
          onClose={vi.fn()}
          onSubmit={vi.fn()}
        />,
      )
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    it('shows "Create drone" title when no drone prop', () => {
      render(
        <DroneFormDialog
          open={true}
          onClose={vi.fn()}
          onSubmit={vi.fn()}
        />,
      )
      const heading = screen.getByRole('heading', { level: 3 })
      expect(heading).toHaveTextContent('Create drone')
    })

    it('shows "Edit drone" title when drone prop is provided', () => {
      render(
        <DroneFormDialog
          open={true}
          drone={mockDrone}
          onClose={vi.fn()}
          onSubmit={vi.fn()}
        />,
      )
      expect(screen.getByText('Edit drone')).toBeInTheDocument()
    })

    it('pre-fills form fields with drone data when editing', () => {
      render(
        <DroneFormDialog
          open={true}
          drone={mockDrone}
          onClose={vi.fn()}
          onSubmit={vi.fn()}
        />,
      )
      expect(screen.getByDisplayValue('Test Drone')).toBeInTheDocument()
      expect(screen.getByDisplayValue('5-inch')).toBeInTheDocument()
      expect(screen.getByDisplayValue('2400')).toBeInTheDocument()
      expect(screen.getByDisplayValue('5.1x3.6x3')).toBeInTheDocument()
      expect(screen.getByDisplayValue('280')).toBeInTheDocument()
      expect(screen.getByDisplayValue('A test description')).toBeInTheDocument()
      expect(screen.getByDisplayValue('Some notes')).toBeInTheDocument()
    })

    it('shows empty form when creating a new drone', () => {
      render(
        <DroneFormDialog
          open={true}
          drone={null}
          onClose={vi.fn()}
          onSubmit={vi.fn()}
        />,
      )
      const inputs = screen.getAllByRole('textbox')
      for (const input of inputs) {
        expect(input).toHaveValue('')
      }
    })

    it('calls onClose when Close button is clicked', async () => {
      const onClose = vi.fn()
      render(
        <DroneFormDialog
          open={true}
          onClose={onClose}
          onSubmit={vi.fn()}
        />,
      )
      await userEvent.click(screen.getAllByText('Close')[0])
      expect(onClose).toHaveBeenCalledOnce()
    })

    it('calls onClose when Cancel button is clicked', async () => {
      const onClose = vi.fn()
      render(
        <DroneFormDialog
          open={true}
          onClose={onClose}
          onSubmit={vi.fn()}
        />,
      )
      await userEvent.click(screen.getByText('Cancel'))
      expect(onClose).toHaveBeenCalledOnce()
    })

    it('calls onClose when backdrop is clicked', async () => {
      const onClose = vi.fn()
      const { container } = render(
        <DroneFormDialog
          open={true}
          onClose={onClose}
          onSubmit={vi.fn()}
        />,
      )
      const backdrop = container.querySelector('.modal-backdrop')!
      await userEvent.click(backdrop)
      expect(onClose).toHaveBeenCalled()
    })

    it('does not close when clicking inside the dialog panel', async () => {
      const onClose = vi.fn()
      const { container } = render(
        <DroneFormDialog
          open={true}
          onClose={onClose}
          onSubmit={vi.fn()}
        />,
      )
      const panel = container.querySelector('.modal-panel')!
      await userEvent.click(panel)
      expect(onClose).not.toHaveBeenCalled()
    })

    it('updates name field when typing', async () => {
      const { container } = render(
        <DroneFormDialog
          open={true}
          onClose={vi.fn()}
          onSubmit={vi.fn()}
        />,
      )
      // The name input is the first text input (required field)
      const nameInput = container.querySelector('input[name="name"]')!
      await userEvent.type(nameInput, 'New Drone')
      expect(screen.getByDisplayValue('New Drone')).toBeInTheDocument()
    })

    it('calls onSubmit with form values on successful submit', async () => {
      const onSubmit = vi.fn().mockResolvedValue(undefined)
      const onClose = vi.fn()
      render(
        <DroneFormDialog
          open={true}
          onClose={onClose}
          onSubmit={onSubmit}
        />,
      )

      const nameInput = screen.getAllByRole('textbox')[0]
      await userEvent.type(nameInput, 'My Drone')

      const submitButton = screen.getByRole('button', { name: 'Create drone' })
      await userEvent.click(submitButton)

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledOnce()
      })

      expect(onClose).toHaveBeenCalledOnce()
    })

    it('shows "Save changes" submit button when editing', () => {
      render(
        <DroneFormDialog
          open={true}
          drone={mockDrone}
          onClose={vi.fn()}
          onSubmit={vi.fn()}
        />,
      )
      expect(screen.getByRole('button', { name: 'Save changes' })).toBeInTheDocument()
    })

    it('shows "Saving..." and disables button while submitting', async () => {
      let resolve: () => void
      const onSubmit = vi.fn().mockReturnValue(new Promise<void>((res) => { resolve = res }))

      render(
        <DroneFormDialog
          open={true}
          drone={mockDrone}
          onClose={vi.fn()}
          onSubmit={onSubmit}
        />,
      )

      const submitButton = screen.getByRole('button', { name: 'Save changes' })
      fireEvent.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText('Saving...')).toBeInTheDocument()
      })

      const savingButton = screen.getByRole('button', { name: 'Saving...' })
      expect(savingButton).toBeDisabled()

      resolve!()
    })

    it('shows error message when onSubmit throws', async () => {
      const onSubmit = vi.fn().mockRejectedValue(new Error('Server error'))
      render(
        <DroneFormDialog
          open={true}
          drone={mockDrone}
          onClose={vi.fn()}
          onSubmit={onSubmit}
        />,
      )

      const submitButton = screen.getByRole('button', { name: 'Save changes' })
      await userEvent.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText('Server error')).toBeInTheDocument()
      })
    })

    it('shows fallback error message when onSubmit throws a non-Error', async () => {
      const onSubmit = vi.fn().mockRejectedValue('Unknown problem')
      render(
        <DroneFormDialog
          open={true}
          drone={mockDrone}
          onClose={vi.fn()}
          onSubmit={onSubmit}
        />,
      )

      const submitButton = screen.getByRole('button', { name: 'Save changes' })
      await userEvent.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText('Unable to save drone.')).toBeInTheDocument()
      })
    })

    it('resets form values when reopened with different drone', async () => {
      const { rerender } = render(
        <DroneFormDialog
          open={false}
          drone={null}
          onClose={vi.fn()}
          onSubmit={vi.fn()}
        />,
      )

      rerender(
        <DroneFormDialog
          open={true}
          drone={mockDrone}
          onClose={vi.fn()}
          onSubmit={vi.fn()}
        />,
      )

      expect(screen.getByDisplayValue('Test Drone')).toBeInTheDocument()
    })

    it('clears error when reopened', async () => {
      const onSubmit = vi.fn().mockRejectedValue(new Error('Bad error'))
      const { rerender } = render(
        <DroneFormDialog
          open={true}
          drone={mockDrone}
          onClose={vi.fn()}
          onSubmit={onSubmit}
        />,
      )

      await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))
      await waitFor(() => expect(screen.getByText('Bad error')).toBeInTheDocument())

      rerender(
        <DroneFormDialog
          open={false}
          drone={mockDrone}
          onClose={vi.fn()}
          onSubmit={onSubmit}
        />,
      )
      rerender(
        <DroneFormDialog
          open={true}
          drone={mockDrone}
          onClose={vi.fn()}
          onSubmit={onSubmit}
        />,
      )

      expect(screen.queryByText('Bad error')).not.toBeInTheDocument()
    })

    it('handles drone with null optional fields gracefully', () => {
      const droneWithNulls: Drone = {
        ...mockDrone,
        description: null,
        frame_size: null,
        motor_kv: null,
        prop_size: null,
        weight_g: null,
        notes: null,
      }

      render(
        <DroneFormDialog
          open={true}
          drone={droneWithNulls}
          onClose={vi.fn()}
          onSubmit={vi.fn()}
        />,
      )

      expect(screen.getByDisplayValue('Test Drone')).toBeInTheDocument()
    })
  })
})