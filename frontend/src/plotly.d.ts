declare module 'plotly.js-dist-min' {
  const Plotly: {
    react: (...args: unknown[]) => void
    purge: (...args: unknown[]) => void
  }

  export default Plotly
}