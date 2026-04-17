import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'

interface PlotlyChartProps {
  data: Array<Record<string, unknown>>
  layout?: Record<string, unknown>
  config?: Record<string, unknown>
  className?: string
}

/**
 * Renders a Plotly chart into a container div using the provided traces and optional layout/config overrides.
 *
 * The component applies sensible default layout and config values (responsive behavior, hidden mode bar,
 * transparent background, font and margin defaults) which are overridden by the supplied `layout` and `config`.
 * The Plotly instance is cleaned up when the component unmounts or when `data`, `layout`, or `config` change.
 *
 * @param data - Array of Plotly trace objects to render
 * @param layout - Optional layout overrides merged with the component's default layout
 * @param config - Optional Plotly config overrides merged with the component's default config
 * @param className - Optional CSS class for the chart container; defaults to `'chart-surface'`
 * @returns A JSX element containing the div that hosts the Plotly chart
 */
export function PlotlyChart({ data, layout, config, className }: PlotlyChartProps) {
  const elementRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!elementRef.current) {
      return
    }

    Plotly.react(elementRef.current, data, {
      autosize: true,
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(255,255,255,0.02)',
      font: { color: '#d7d8d3', family: 'Segoe UI, sans-serif' },
      margin: { l: 48, r: 20, t: 28, b: 42 },
      ...layout,
    }, {
      displayModeBar: false,
      responsive: true,
      ...config,
    })

    return () => {
      if (elementRef.current) {
        Plotly.purge(elementRef.current)
      }
    }
  }, [config, data, layout])

  return <div className={className ?? 'chart-surface'} ref={elementRef} />
}