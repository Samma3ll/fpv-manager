import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PlotlyChart } from './PlotlyChart'

vi.mock('plotly.js-dist-min', () => ({
  default: {
    react: vi.fn().mockResolvedValue(undefined),
    purge: vi.fn(),
  },
}))

import Plotly from 'plotly.js-dist-min'

describe('PlotlyChart', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders a div container', () => {
    const { container } = render(<PlotlyChart data={[]} />)
    const div = container.querySelector('div')
    expect(div).toBeInTheDocument()
  })

  it('applies default className "chart-surface" when no className provided', () => {
    const { container } = render(<PlotlyChart data={[]} />)
    expect(container.firstChild).toHaveClass('chart-surface')
  })

  it('applies custom className when provided', () => {
    const { container } = render(<PlotlyChart data={[]} className="my-chart" />)
    expect(container.firstChild).toHaveClass('my-chart')
    expect(container.firstChild).not.toHaveClass('chart-surface')
  })

  it('calls Plotly.react on mount', () => {
    render(<PlotlyChart data={[{ type: 'scatter', x: [1, 2], y: [3, 4] }]} />)
    expect(Plotly.react).toHaveBeenCalledOnce()
  })

  it('calls Plotly.react with the provided data', () => {
    const data = [{ type: 'scatter', x: [1, 2, 3], y: [4, 5, 6] }]
    render(<PlotlyChart data={data} />)
    expect(Plotly.react).toHaveBeenCalledWith(
      expect.any(HTMLDivElement),
      data,
      expect.objectContaining({ autosize: true }),
      expect.objectContaining({ displayModeBar: false }),
    )
  })

  it('merges provided layout with default layout', () => {
    const customLayout = { title: 'My Chart' }
    render(<PlotlyChart data={[]} layout={customLayout} />)
    expect(Plotly.react).toHaveBeenCalledWith(
      expect.any(HTMLDivElement),
      [],
      expect.objectContaining({ autosize: true, title: 'My Chart' }),
      expect.any(Object),
    )
  })

  it('merges provided config with default config', () => {
    const customConfig = { scrollZoom: true }
    render(<PlotlyChart data={[]} config={customConfig} />)
    expect(Plotly.react).toHaveBeenCalledWith(
      expect.any(HTMLDivElement),
      [],
      expect.any(Object),
      expect.objectContaining({ displayModeBar: false, scrollZoom: true }),
    )
  })

  it('passes default layout properties', () => {
    render(<PlotlyChart data={[]} />)
    expect(Plotly.react).toHaveBeenCalledWith(
      expect.any(HTMLDivElement),
      [],
      expect.objectContaining({
        autosize: true,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(255,255,255,0.02)',
      }),
      expect.any(Object),
    )
  })

  it('unmounts without throwing an error', () => {
    const { unmount } = render(<PlotlyChart data={[]} />)
    expect(() => unmount()).not.toThrow()
  })

  it('re-renders without error when data changes', () => {
    const { rerender } = render(<PlotlyChart data={[]} />)
    rerender(<PlotlyChart data={[{ type: 'bar', x: [1], y: [2] }]} />)
    expect(Plotly.react).toHaveBeenCalledTimes(2)
  })

  it('handles empty data array without error', () => {
    expect(() => render(<PlotlyChart data={[]} />)).not.toThrow()
  })
})