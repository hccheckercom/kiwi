import { useState, useEffect } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import axios from 'axios'
import DependencyGraph from './components/DependencyGraph'
import RiskHeatmap from './components/RiskHeatmap'
import ApprovalWorkflow from './components/ApprovalWorkflow'
import { ScanProgress } from './components/ScanProgress'
import { TrendsChart } from './components/TrendsChart'
import { Login } from './components/Login'
import { useWebSocket } from './hooks/useWebSocket'
import './App.css'

const queryClient = new QueryClient()

function Dashboard() {
  const [activeTab, setActiveTab] = useState<'graph' | 'heatmap' | 'approval' | 'trends'>('graph')
  const { connected, lastMessage } = useWebSocket('ws://localhost:8000/ws')
  const [scanProgress, setScanProgress] = useState({
    patternsChecked: 0,
    totalPatterns: 0,
    violationsFound: 0,
    isScanning: false
  })

  useEffect(() => {
    if (lastMessage?.type === 'scan_progress') {
      setScanProgress({
        patternsChecked: lastMessage.patterns_checked || 0,
        totalPatterns: lastMessage.total_patterns || 0,
        violationsFound: lastMessage.violations_found || 0,
        isScanning: true
      })
    } else if (lastMessage?.type === 'scan_complete') {
      setScanProgress(prev => ({
        ...prev,
        isScanning: false
      }))
    }
  }, [lastMessage])

  return (
    <div className="app">
      <header className="app-header">
        <h1>Kiwi Agent Dashboard</h1>
        <div className="connection-status">
          <span className={`status-dot ${connected ? 'connected' : 'disconnected'}`} />
          {connected ? 'Connected' : 'Disconnected'}
        </div>
      </header>

      <nav className="app-nav">
        <button
          className={activeTab === 'graph' ? 'active' : ''}
          onClick={() => setActiveTab('graph')}
        >
          Dependency Graph
        </button>
        <button
          className={activeTab === 'heatmap' ? 'active' : ''}
          onClick={() => setActiveTab('heatmap')}
        >
          Risk Heatmap
        </button>
        <button
          className={activeTab === 'approval' ? 'active' : ''}
          onClick={() => setActiveTab('approval')}
        >
          Approval Workflow
        </button>
        <button
          className={activeTab === 'trends' ? 'active' : ''}
          onClick={() => setActiveTab('trends')}
        >
          Trends
        </button>
      </nav>

      {scanProgress.isScanning && (
        <ScanProgress
          patternsChecked={scanProgress.patternsChecked}
          totalPatterns={scanProgress.totalPatterns}
          violationsFound={scanProgress.violationsFound}
          isScanning={scanProgress.isScanning}
        />
      )}

      <main className="app-main">
        {activeTab === 'graph' && <DependencyGraph />}
        {activeTab === 'heatmap' && <RiskHeatmap />}
        {activeTab === 'approval' && <ApprovalWorkflow />}
        {activeTab === 'trends' && <TrendsChart projectName="wezone-plugins" />}
      </main>

      {lastMessage && (
        <div className="notification">
          {lastMessage.type}: {lastMessage.message}
        </div>
      )}
    </div>
  )
}

function App() {
  const [token, setToken] = useState<string | null>(
    localStorage.getItem('kiwi_token')
  )
  const [isAuthenticated, setIsAuthenticated] = useState(!!token)

  useEffect(() => {
    // Setup axios interceptor for token
    const requestInterceptor = axios.interceptors.request.use((config) => {
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    })

    // Setup response interceptor for 401 errors
    const responseInterceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('kiwi_token')
          setToken(null)
          setIsAuthenticated(false)
        }
        return Promise.reject(error)
      }
    )

    return () => {
      axios.interceptors.request.eject(requestInterceptor)
      axios.interceptors.response.eject(responseInterceptor)
    }
  }, [token])

  const handleLogin = (newToken: string) => {
    setToken(newToken)
    setIsAuthenticated(true)
  }

  return (
    <QueryClientProvider client={queryClient}>
      {isAuthenticated ? <Dashboard /> : <Login onLogin={handleLogin} />}
    </QueryClientProvider>
  )
}

export default App
