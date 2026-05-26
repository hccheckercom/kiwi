export interface Violation {
  lesson_id: string
  file: string
  line: number
  severity: 'CRITICAL' | 'HIGH' | 'SUGGEST'
  title: string
  match_text?: string
}

export interface Task {
  id: string
  violation: Violation
  effort: 'low' | 'medium' | 'high'
  risk: number
  priority: number
  dependencies: string[]
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
}

export interface ExecutionStage {
  stage: number
  tasks: Task[]
  can_parallel: boolean
}

export interface DependencyNode {
  id: string
  label: string
  type: 'file' | 'task'
  severity?: string
}

export interface DependencyLink {
  source: string
  target: string
  type: 'depends_on' | 'blocks'
}

export interface RiskData {
  file: string
  risk_score: number
  violations: number
  severity_breakdown: {
    CRITICAL: number
    HIGH: number
    SUGGEST: number
  }
}

export interface Checkpoint {
  checkpoint_id: string
  agent_run_id: number
  message: string
  options: Array<{id: string, label: string, description?: string}>
  created_at: string
  resolved_at?: string
  decision?: string
  comment?: string
}
