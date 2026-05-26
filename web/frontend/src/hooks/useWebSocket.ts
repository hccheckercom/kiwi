import { useEffect, useState, useRef } from 'react'

interface WebSocketMessage {
  type: string
  message?: string
  data?: any
  patterns_checked?: number
  total_patterns?: number
  violations_found?: number
}

export function useWebSocket(url: string) {
  const [connected, setConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    let ws: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let connectTimer: ReturnType<typeof setTimeout> | null = null
    let isVisible = true
    let isMounted = true

    const connect = () => {
      if (!isMounted || (ws && ws.readyState === WebSocket.OPEN)) {
        return
      }

      ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (!isMounted) {
          ws?.close()
          return
        }
        setConnected(true)
        console.log('WebSocket connected')
      }

      ws.onmessage = (event) => {
        if (!isMounted) return
        try {
          const data = JSON.parse(event.data)
          setLastMessage(data)
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e)
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
      }

      ws.onclose = () => {
        if (!isMounted) return
        setConnected(false)
        console.log('WebSocket disconnected')

        if (isVisible && !reconnectTimer && isMounted) {
          reconnectTimer = setTimeout(() => {
            reconnectTimer = null
            connect()
          }, 2000)
        }
      }
    }

    const handleVisibilityChange = () => {
      isVisible = !document.hidden

      if (isVisible) {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
          console.log('Tab visible, reconnecting WebSocket...')
          connect()
        }
      } else {
        if (ws && ws.readyState === WebSocket.OPEN) {
          console.log('Tab hidden, closing WebSocket')
          ws.close()
        }
        if (reconnectTimer) {
          clearTimeout(reconnectTimer)
          reconnectTimer = null
        }
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)

    connectTimer = setTimeout(() => {
      connectTimer = null
      connect()
    }, 100)

    return () => {
      isMounted = false
      isVisible = false
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      if (connectTimer) clearTimeout(connectTimer)
      if (reconnectTimer) clearTimeout(reconnectTimer)
      if (ws) ws.close()
    }
  }, [url])

  const sendMessage = (message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }

  return { connected, lastMessage, sendMessage }
}
