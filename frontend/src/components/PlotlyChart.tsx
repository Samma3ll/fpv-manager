import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'

interface PlotlyChartProps {
  data: Array<Record<string, unknown>>
  layout?: Record<string, unknown>
  config?: Record<string, unknown>
  className?: string
}

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