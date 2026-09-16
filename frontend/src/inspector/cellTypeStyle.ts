/** Neuron identity colours (BIOLOGICAL DATA channel). Activity uses a separate channel. */
const KNOWN: Record<string, string> = {
  LC4: '#4cc9f0',
  LPLC2: '#2ec4b6',
  DNp01: '#ff9f43',
}
const FALLBACK = ['#a3b18a', '#e0aaff', '#ffd166', '#b5b8c9', '#8ecae6', '#cdb4db']

export function cellTypeColor(cellType: string | null, cellTypes: string[]): string {
  const type = cellType ?? 'unknown'
  const known = KNOWN[type]
  if (known) return known
  const others = cellTypes.filter((t) => !(t in KNOWN))
  const index = Math.max(others.indexOf(type), 0)
  return FALLBACK[index % FALLBACK.length] ?? '#b5b8c9'
}

export function cellTypeDescription(cellType: string | null): string {
  switch (cellType) {
    case 'LC4':
      return 'LC4 — lobula columnar visual projection neuron (looming-responsive, literature)'
    case 'LPLC2':
      return 'LPLC2 — lobula plate/lobula columnar visual projection neuron (looming-responsive, literature)'
    case 'DNp01':
      return 'DNp01 — giant fiber descending neuron (escape / takeoff, literature)'
    default:
      return cellType ? `${cellType} (cell type from the dataset annotations)` : 'cell type not available'
  }
}
