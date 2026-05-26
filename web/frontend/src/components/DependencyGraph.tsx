import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import axios from 'axios'
import type { DependencyNode, DependencyLink } from '../types'
import './DependencyGraph.css'

export default function DependencyGraph() {
  const svgRef = useRef<SVGSVGElement>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [graphData, setGraphData] = useState<{ nodes: DependencyNode[], links: DependencyLink[] } | null>(null)
  const [selectedNode, setSelectedNode] = useState<any>(null)
  const hasLoadedRef = useRef(false)

  useEffect(() => {
    if (!hasLoadedRef.current) {
      hasLoadedRef.current = true
      console.log('DependencyGraph mounted, calling loadGraph()')
      loadGraph()
    }
  }, [])

  // Render graph when data is ready AND SVG ref is available
  useEffect(() => {
    if (!loading && graphData && svgRef.current) {
      console.log('useEffect: rendering graph with', graphData.nodes.length, 'nodes')
      renderGraph(graphData.nodes, graphData.links)
    }
  }, [loading, graphData])

  async function loadGraph() {
    try {
      setLoading(true)
      setError(null)
      console.log('Calling /api/plan...')

      const response = await axios.post('http://localhost:8000/api/plan', {
        path: 'D:\\projects\\wezone\\.claude\\kiwi\\web',
        severity: 'CRITICAL',
        max_fixes: 3
      }, {
        timeout: 60000 // 1 minute timeout
      })

      console.log('API response:', response.data)
      const { dependency_graph } = response.data
      console.log('Nodes:', dependency_graph.nodes)
      console.log('Links:', dependency_graph.links)

      setGraphData(dependency_graph)
      setLoading(false)
    } catch (err) {
      console.error('Load graph error:', err)
      if (axios.isAxiosError(err) && err.code === 'ECONNABORTED') {
        setError('Request timeout - scan took too long (>2 min)')
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load graph')
      }
      setLoading(false)
    }
  }

  function renderGraph(nodes: DependencyNode[], links: DependencyLink[]) {
    console.log('renderGraph called with', nodes.length, 'nodes')

    if (!svgRef.current) {
      console.error('svgRef.current is null!')
      return
    }

    const width = svgRef.current.clientWidth
    const height = svgRef.current.clientHeight

    console.log('SVG dimensions:', width, 'x', height)

    if (width === 0 || height === 0) {
      console.error('SVG has zero dimensions! width:', width, 'height:', height)
      return
    }

    d3.select(svgRef.current).selectAll('*').remove()

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height)

    // Add initial positions to nodes
    const nodesWithPositions = nodes.map((d) => ({
      ...d,
      x: width / 2 + (Math.random() - 0.5) * 100,
      y: height / 2 + (Math.random() - 0.5) * 100
    }))

    const simulation = d3.forceSimulation(nodesWithPositions as any)
      .force('link', d3.forceLink(links).id((d: any) => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(30))

    const link = svg.append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', '#666')
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', (d: DependencyLink) => d.type === 'blocks' ? '5,5' : '0')

    const node = svg.append('g')
      .selectAll('circle')
      .data(nodesWithPositions)
      .join('circle')
      .attr('r', 20)
      .attr('fill', (d: any) => {
        if (d.severity === 'CRITICAL') return '#ef4444'
        if (d.severity === 'HIGH') return '#f59e0b'
        return '#3b82f6'
      })
      .style('cursor', 'pointer')
      .on('click', (event: any, d: any) => {
        event.stopPropagation()
        setSelectedNode(d)
      })
      .call(d3.drag<any, any>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended) as any)

    const label = svg.append('g')
      .selectAll('text')
      .data(nodesWithPositions)
      .join('text')
      .text((d: any) => d.label)
      .attr('font-size', 10)
      .attr('fill', '#fff')
      .attr('text-anchor', 'middle')
      .attr('dy', 35)

    simulation.on('tick', () => {
      console.log('Tick fired, node count:', node.size(), 'first node pos:', nodesWithPositions[0])

      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y)

      node
        .attr('cx', (d: any) => d.x)
        .attr('cy', (d: any) => d.y)

      label
        .attr('x', (d: any) => d.x)
        .attr('y', (d: any) => d.y)
    })

    console.log('Node selection size:', node.size())
    console.log('Node data:', node.data())

    function dragstarted(event: any) {
      if (!event.active) simulation.alphaTarget(0.3).restart()
      event.subject.fx = event.subject.x
      event.subject.fy = event.subject.y
    }

    function dragged(event: any) {
      event.subject.fx = event.x
      event.subject.fy = event.y
    }

    function dragended(event: any) {
      if (!event.active) simulation.alphaTarget(0)
      event.subject.fx = null
      event.subject.fy = null
    }
  }

  const copyToClipboard = async () => {
    if (!selectedNode) return

    const text = `Violation Details:

Lesson: ${selectedNode.lesson_id}
File: ${selectedNode.file}
Line: ${selectedNode.line || 'N/A'}
Severity: ${selectedNode.severity}
Category: ${selectedNode.category || 'N/A'}
Description: ${selectedNode.description}

Effort: ${selectedNode.effort} min
Risk: ${(selectedNode.risk * 100).toFixed(0)}%

Fix Command:
kiwi_fix({ lesson_id: "${selectedNode.lesson_id}", file: "${selectedNode.file}", line: ${selectedNode.line || 0}, apply: false })
`

    try {
      await navigator.clipboard.writeText(text)
      alert('Copied to clipboard!')
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  if (loading) return <div className="loading">Loading dependency graph...</div>
  if (error) return <div className="error">Error: {error}</div>

  return (
    <div className="dependency-graph">
      <div className="graph-header">
        <h2>Dependency Graph</h2>
        <button onClick={loadGraph}>Refresh</button>
      </div>
      <svg ref={svgRef} className="graph-svg" />
      <div className="graph-legend">
        <div className="legend-item">
          <span className="legend-dot critical" />
          CRITICAL
        </div>
        <div className="legend-item">
          <span className="legend-dot high" />
          HIGH
        </div>
        <div className="legend-item">
          <span className="legend-dot normal" />
          SUGGEST
        </div>
      </div>

      {selectedNode && (
        <div className="violation-modal" onClick={() => setSelectedNode(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Violation Details</h3>
              <button className="close-btn" onClick={() => setSelectedNode(null)}>×</button>
            </div>
            <div className="modal-body">
              <div className="detail-row">
                <span className="label">Lesson:</span>
                <span className="value">{selectedNode.lesson_id}</span>
              </div>
              <div className="detail-row">
                <span className="label">File:</span>
                <span className="value">{selectedNode.file}</span>
              </div>
              <div className="detail-row">
                <span className="label">Line:</span>
                <span className="value">{selectedNode.line || 'N/A'}</span>
              </div>
              <div className="detail-row">
                <span className="label">Severity:</span>
                <span className={`value severity-${selectedNode.severity.toLowerCase()}`}>{selectedNode.severity}</span>
              </div>
              <div className="detail-row">
                <span className="label">Category:</span>
                <span className="value">{selectedNode.category || 'N/A'}</span>
              </div>
              <div className="detail-row full">
                <span className="label">Description:</span>
                <span className="value">{selectedNode.description}</span>
              </div>
              <div className="detail-row">
                <span className="label">Effort:</span>
                <span className="value">{selectedNode.effort} min</span>
              </div>
              <div className="detail-row">
                <span className="label">Risk:</span>
                <span className="value">{(selectedNode.risk * 100).toFixed(0)}%</span>
              </div>
            </div>
            <div className="modal-footer">
              <button className="copy-btn" onClick={copyToClipboard}>Copy Bug & Fix</button>
              <button className="close-btn-secondary" onClick={() => setSelectedNode(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
