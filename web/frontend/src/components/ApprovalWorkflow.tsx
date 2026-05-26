import { useEffect, useState } from 'react'
import axios from 'axios'
import type { Checkpoint } from '../types'
import './ApprovalWorkflow.css'

export default function ApprovalWorkflow() {
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedCheckpoint, setSelectedCheckpoint] = useState<Checkpoint | null>(null)
  const [comment, setComment] = useState('')

  useEffect(() => {
    loadCheckpoints()
    const interval = setInterval(loadCheckpoints, 5000)
    return () => clearInterval(interval)
  }, [])

  async function loadCheckpoints() {
    try {
      const response = await axios.get('http://localhost:8000/api/checkpoints')
      setCheckpoints(response.data.checkpoints || [])
      setLoading(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load checkpoints')
      setLoading(false)
    }
  }

  async function handleApproval(checkpoint: Checkpoint, decision: string) {
    try {
      await axios.post(`http://localhost:8000/api/checkpoint/${checkpoint.checkpoint_id}/resolve`, {
        decision,
        comment: comment || undefined
      })

      setCheckpoints(prev => prev.filter(cp => cp.checkpoint_id !== checkpoint.checkpoint_id))
      setSelectedCheckpoint(null)
      setComment('')
    } catch (err) {
      alert('Failed to submit approval: ' + (err instanceof Error ? err.message : 'Unknown error'))
    }
  }

  if (loading) return <div className="loading">Loading approval workflow...</div>
  if (error) return <div className="error">Error: {error}</div>

  return (
    <div className="approval-workflow">
      <div className="workflow-header">
        <h2>Approval Workflow</h2>
        <div className="pending-count">
          {checkpoints.length} pending approval{checkpoints.length !== 1 ? 's' : ''}
        </div>
      </div>

      {checkpoints.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">✓</div>
          <div className="empty-text">No pending approvals</div>
          <div className="empty-subtext">All agent actions have been approved or completed</div>
        </div>
      ) : (
        <div className="checkpoints-list">
          {checkpoints.map((checkpoint) => (
            <div
              key={checkpoint.checkpoint_id}
              className={`checkpoint-card ${selectedCheckpoint?.checkpoint_id === checkpoint.checkpoint_id ? 'selected' : ''}`}
              onClick={() => setSelectedCheckpoint(checkpoint)}
            >
              <div className="checkpoint-header">
                <div className="checkpoint-id">Checkpoint {checkpoint.checkpoint_id}</div>
                <div className="checkpoint-agent">Agent Run #{checkpoint.agent_run_id}</div>
              </div>
              <div className="checkpoint-message">{checkpoint.message}</div>
              <div className="checkpoint-time">
                {new Date(checkpoint.created_at).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      )}

      {selectedCheckpoint && (
        <div className="approval-panel">
          <div className="panel-header">
            <h3>Review Checkpoint {selectedCheckpoint.checkpoint_id}</h3>
            <button
              className="close-button"
              onClick={() => setSelectedCheckpoint(null)}
            >
              ×
            </button>
          </div>

          <div className="panel-content">
            <div className="checkpoint-details">
              <div className="detail-row">
                <span className="detail-label">Agent Run:</span>
                <span className="detail-value">#{selectedCheckpoint.agent_run_id}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Created:</span>
                <span className="detail-value">
                  {new Date(selectedCheckpoint.created_at).toLocaleString()}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Message:</span>
                <span className="detail-value">{selectedCheckpoint.message}</span>
              </div>
            </div>

            <div className="options-section">
              <h4>Available Options</h4>
              <div className="options-list">
                {selectedCheckpoint.options.map((option) => (
                  <button
                    key={option.id}
                    className="option-button"
                    onClick={() => handleApproval(selectedCheckpoint, option.id)}
                    title={option.description}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="comment-section">
              <label htmlFor="comment">Comment (optional)</label>
              <textarea
                id="comment"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Add a comment about your decision..."
                rows={3}
              />
            </div>

            <div className="action-buttons">
              <button
                className="approve-button"
                onClick={() => handleApproval(selectedCheckpoint, 'approve')}
              >
                Approve
              </button>
              <button
                className="reject-button"
                onClick={() => handleApproval(selectedCheckpoint, 'reject')}
              >
                Reject
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
