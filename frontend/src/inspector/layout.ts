import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type SimulationLinkDatum, type SimulationNodeDatum } from 'd3-force'

import type { CircuitEdgeRecord, CircuitNodeRecord } from '../api/types.ts'

/** Normalised layout space; the graph component scales it to the rendered size. */
export const LAYOUT_WIDTH = 1000
export const LAYOUT_HEIGHT = 700

export interface NodePosition {
  x: number
  y: number
}

interface LayoutNode extends SimulationNodeDatum {
  id: string
  tx: number
  ty: number
}

/**
 * Deterministic layout of the loaded circuit: columns by side (L / R / unknown), bands by
 * role and cell type (sensory on top, other in the middle, output at the bottom), then a
 * short force relaxation for collision avoidance. Positions are presentation only; they
 * carry no anatomical meaning.
 */
export function computeLayout(nodes: CircuitNodeRecord[], edges: CircuitEdgeRecord[]): Map<string, NodePosition> {
  const columnX = (side: string | null): number => (side === 'L' ? 0.28 : side === 'R' ? 0.72 : 0.5) * LAYOUT_WIDTH
  const bands = new Map<string, number>()
  const typesByRole: Record<string, string[]> = { sensory: [], other: [], output: [] }
  for (const node of nodes) {
    const role = node.role === 'sensory' || node.role === 'output' ? node.role : 'other'
    const type = node.cell_type ?? 'unknown'
    const list = typesByRole[role] ?? (typesByRole[role] = [])
    if (!list.includes(type)) list.push(type)
  }
  for (const role of ['sensory', 'other', 'output'] as const) typesByRole[role]?.sort()
  const ordered: string[] = [
    ...(typesByRole['sensory'] ?? []).map((t) => `sensory:${t}`),
    ...(typesByRole['other'] ?? []).map((t) => `other:${t}`),
    ...(typesByRole['output'] ?? []).map((t) => `output:${t}`),
  ]
  const rows = Math.max(ordered.length, 1)
  ordered.forEach((key, index) => {
    const y = rows === 1 ? 0.5 : 0.14 + (0.72 * index) / (rows - 1)
    bands.set(key, y * LAYOUT_HEIGHT)
  })

  const layoutNodes: LayoutNode[] = nodes.map((node, index) => {
    const role = node.role === 'sensory' || node.role === 'output' ? node.role : 'other'
    const key = `${role}:${node.cell_type ?? 'unknown'}`
    const tx = columnX(node.side)
    const ty = bands.get(key) ?? LAYOUT_HEIGHT / 2
    // spread members of a band on a ring so the relaxation starts from a tidy state
    const angle = (index * 2.399963) % (2 * Math.PI)
    const spread = role === 'output' ? 6 : 70
    return { id: node.neuron_id, tx, ty, x: tx + Math.cos(angle) * spread, y: ty + Math.sin(angle) * spread * 0.55 }
  })
  const byId = new Map(layoutNodes.map((n) => [n.id, n]))
  const links: SimulationLinkDatum<LayoutNode>[] = edges
    .filter((e) => byId.has(e.pre_neuron_id) && byId.has(e.post_neuron_id))
    .map((e) => ({ source: e.pre_neuron_id, target: e.post_neuron_id }))

  const simulation = forceSimulation(layoutNodes)
    .force('x', forceX<LayoutNode>((d) => d.tx).strength(0.12))
    .force('y', forceY<LayoutNode>((d) => d.ty).strength(0.2))
    .force('collide', forceCollide<LayoutNode>(9).strength(0.9))
    .force('charge', forceManyBody<LayoutNode>().strength(-6))
    .force('link', forceLink<LayoutNode, SimulationLinkDatum<LayoutNode>>(links).id((d) => d.id).strength(0.005).distance(120))
    .stop()
  simulation.tick(220)

  const positions = new Map<string, NodePosition>()
  for (const node of layoutNodes) {
    const x = Math.min(Math.max(node.x ?? node.tx, 20), LAYOUT_WIDTH - 20)
    const y = Math.min(Math.max(node.y ?? node.ty, 20), LAYOUT_HEIGHT - 20)
    positions.set(node.id, { x, y })
  }
  return positions
}
