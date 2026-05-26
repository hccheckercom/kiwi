import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import * as d3 from 'd3';
import './TrendsChart.css';

interface TrendsData {
  timestamp: string;
  critical: number;
  high: number;
  suggest: number;
}

interface TrendsChartProps {
  projectName: string;
}

export function TrendsChart({ projectName }: TrendsChartProps) {
  const [data, setData] = useState<TrendsData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`http://localhost:8000/api/trends/${projectName}?days=30`);
        setData(response.data.trends);
        setError('');
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load trends');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [projectName]);

  useEffect(() => {
    if (!data.length || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    const width = 800;
    const height = 400;
    const margin = { top: 20, right: 120, bottom: 30, left: 40 };

    svg.selectAll('*').remove();

    const x = d3.scaleTime()
      .domain(d3.extent(data, d => new Date(d.timestamp)) as [Date, Date])
      .range([margin.left, width - margin.right]);

    const y = d3.scaleLinear()
      .domain([0, d3.max(data, d => d.critical + d.high + d.suggest) || 0])
      .nice()
      .range([height - margin.bottom, margin.top]);

    const lineCritical = d3.line<TrendsData>()
      .x(d => x(new Date(d.timestamp)))
      .y(d => y(d.critical));

    const lineHigh = d3.line<TrendsData>()
      .x(d => x(new Date(d.timestamp)))
      .y(d => y(d.high));

    const lineSuggest = d3.line<TrendsData>()
      .x(d => x(new Date(d.timestamp)))
      .y(d => y(d.suggest));

    svg.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', '#dc3545')
      .attr('stroke-width', 2)
      .attr('d', lineCritical);

    svg.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', '#ffc107')
      .attr('stroke-width', 2)
      .attr('d', lineHigh);

    svg.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', '#17a2b8')
      .attr('stroke-width', 2)
      .attr('d', lineSuggest);

    svg.append('g')
      .attr('transform', `translate(0,${height - margin.bottom})`)
      .call(d3.axisBottom(x));

    svg.append('g')
      .attr('transform', `translate(${margin.left},0)`)
      .call(d3.axisLeft(y));

    const legend = svg.append('g')
      .attr('transform', `translate(${width - margin.right + 10}, ${margin.top})`);

    const legendData = [
      { label: 'Critical', color: '#dc3545' },
      { label: 'High', color: '#ffc107' },
      { label: 'Suggest', color: '#17a2b8' }
    ];

    legendData.forEach((item, i) => {
      const g = legend.append('g')
        .attr('transform', `translate(0, ${i * 20})`);

      g.append('line')
        .attr('x1', 0)
        .attr('x2', 20)
        .attr('y1', 0)
        .attr('y2', 0)
        .attr('stroke', item.color)
        .attr('stroke-width', 2);

      g.append('text')
        .attr('x', 25)
        .attr('y', 4)
        .attr('font-size', '12px')
        .text(item.label);
    });
  }, [data]);

  if (loading) {
    return <div className="trends-loading">Loading trends...</div>;
  }

  if (error) {
    return <div className="trends-error">{error}</div>;
  }

  if (!data.length) {
    return <div className="trends-empty">No scan history available</div>;
  }

  return (
    <div className="trends-chart">
      <h3>Violation Trends (Last 30 Days)</h3>
      <svg ref={svgRef} width={800} height={400} />
    </div>
  );
}