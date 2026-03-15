import { useState, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import ChatWindow from './components/ChatWindow'
import InputBar from './components/InputBar'
import styles from './App.module.css'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:5050'

function nowTs() {
  return new Date().toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

export default function App() {
  const [conversations, setConversations] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [loading, setLoading] = useState(false)

  const activeConversation = conversations.find((c) => c.id === activeId) ?? null

  const handleNew = useCallback(() => {
    setActiveId(null)
  }, [])

  const handleDelete = useCallback((id) => {
    setConversations((prev) => prev.filter((c) => c.id !== id))
    setActiveId((prev) => (prev === id ? null : prev))
  }, [])

  const handleSend = useCallback(
    async (text) => {
      const ts = nowTs()
      const userMsgId = `msg-${Date.now()}`
      const agentMsgId = `msg-${Date.now() + 1}`

      const userMsg = { id: userMsgId, role: 'user', content: text, timestamp: ts }
      const pendingMsg = { id: agentMsgId, role: 'assistant', phases: [], streaming: true, timestamp: ts }

      let convId = activeId

      if (!convId) {
        convId = `c-${Date.now()}`
        setActiveId(convId)
        setConversations((prev) => [
          {
            id: convId,
            title: text.length > 48 ? text.slice(0, 48) + '…' : text,
            timestamp: ts,
            severity: 'info',
            messages: [userMsg, pendingMsg],
          },
          ...prev,
        ])
      } else {
        setConversations((prev) =>
          prev.map((c) =>
            c.id === convId ? { ...c, messages: [...c.messages, userMsg, pendingMsg] } : c
          )
        )
      }

      setLoading(true)

      let toolCalls = []
      let agentText = ''

      const flush = (done = false) => {
        const phases = []
        if (toolCalls.length > 0) {
          phases.push({ name: 'investigate', label: 'Investigation', content: toolCalls })
        }
        if (agentText.trim()) {
          phases.push({ name: 'report', label: 'Response', content: agentText.trim() })
        }
        setConversations((prev) =>
          prev.map((c) =>
            c.id === convId
              ? {
                  ...c,
                  messages: c.messages.map((m) =>
                    m.id === agentMsgId ? { ...m, phases, streaming: !done } : m
                  ),
                }
              : c
          )
        )
      }

      try {
        const res = await fetch(`${API_BASE}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text }),
        })

        if (!res.ok) throw new Error(`HTTP ${res.status}`)

        const reader = res.body.getReader()
        const dec = new TextDecoder()
        let buf = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buf += dec.decode(value, { stream: true })
          const lines = buf.split('\n')
          buf = lines.pop() ?? ''

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            const raw = line.slice(6).trim()
            if (!raw) continue
            try {
              const ev = JSON.parse(raw)
              if (ev.type === 'tool_call') {
                for (const call of ev.calls ?? []) {
                  toolCalls = [...toolCalls, { name: call.name, args: call.args ?? {}, result: null }]
                }
                flush()
              } else if (ev.type === 'tool_result') {
                let matched = false
                toolCalls = toolCalls.map((tc) => {
                  if (!matched && tc.name === ev.name && tc.result === null) {
                    matched = true
                    return { ...tc, result: ev.output }
                  }
                  return tc
                })
                flush()
              } else if (ev.type === 'agent') {
                agentText += ev.content
                flush()
              } else if (ev.type === 'done') {
                flush(true)
              }
            } catch {
              // ignore malformed SSE lines
            }
          }
        }

        flush(true)
      } catch (err) {
        console.error('Chat error:', err)
        const phases = [
          {
            name: 'report',
            label: 'Error',
            content: `Could not reach backend.\n\n${err.message}\n\nMake sure the NOC Agent backend is running on ${API_BASE}`,
          },
        ]
        setConversations((prev) =>
          prev.map((c) =>
            c.id === convId
              ? {
                  ...c,
                  messages: c.messages.map((m) =>
                    m.id === agentMsgId ? { ...m, phases, streaming: false } : m
                  ),
                }
              : c
          )
        )
      } finally {
        setLoading(false)
      }
    },
    [activeId]
  )

  return (
    <div className={styles.layout}>
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={setActiveId}
        onNew={handleNew}
        onDelete={handleDelete}
      />
      <div className={styles.main}>
        <Header conversation={activeConversation} />
        <ChatWindow messages={activeConversation?.messages ?? []} />
        <InputBar onSend={handleSend} loading={loading} />
      </div>
    </div>
  )
}
