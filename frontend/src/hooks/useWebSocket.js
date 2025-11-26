import { useState, useEffect, useRef, useCallback } from 'react'

const useWebSocket = (url, { maxBuffer = 200 } = {}) => {
  const [messages, setMessages] = useState([])
  const [lastMessage, setLastMessage] = useState(null)
  const [isConnected, setIsConnected] = useState(false)
  const ws = useRef(null)
  const reconnectTimeout = useRef(null)

  const connect = useCallback(() => {
    try {
      ws.current = new WebSocket(url)

      ws.current.onopen = () => {
        console.log('WebSocket connected')
        setIsConnected(true)
        // Send ping to keep connection alive
        const pingInterval = setInterval(() => {
          if (ws.current?.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify({ command: 'ping' }))
          }
        }, 30000)
        ws.current.pingInterval = pingInterval
      }

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          setLastMessage(data)
          setMessages((prev) => {
            const next = [...prev, data]
            // Cap buffer to prevent unbounded growth causing freezes
            if (next.length > maxBuffer) {
              return next.slice(next.length - maxBuffer)
            }
            return next
          })
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error)
      }

      ws.current.onclose = () => {
        console.log('WebSocket disconnected')
        setIsConnected(false)
        if (ws.current?.pingInterval) {
          clearInterval(ws.current.pingInterval)
        }
        // Attempt to reconnect after 5 seconds
        reconnectTimeout.current = setTimeout(() => {
          console.log('Attempting to reconnect...')
          connect()
        }, 5000)
      }
    } catch (error) {
      console.error('Failed to connect to WebSocket:', error)
    }
  }, [url])

  useEffect(() => {
    connect()

    return () => {
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current)
      }
      if (ws.current?.pingInterval) {
        clearInterval(ws.current.pingInterval)
      }
      if (ws.current) {
        ws.current.close()
      }
    }
  }, [connect])

  const sendMessage = useCallback((message) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket is not connected')
    }
  }, [])

  return { messages, lastMessage, sendMessage, isConnected }
}

export default useWebSocket
