import { useEffect, useRef } from 'react'
import { ShieldAlert } from 'lucide-react'
import MessageBubble from './MessageBubble'
import { MOCK_MESSAGES } from '../mockData'
import styles from './ChatWindow.module.css'

function EmptyState() {
  return (
    <div className={styles.empty}>
      <div className={styles.emptyIcon}>
        <ShieldAlert size={32} color="var(--accent)" />
      </div>
      <h2 className={styles.emptyTitle}>NOC Agent Ready</h2>
      <p className={styles.emptyDesc}>
        Submit an alert or describe an incident to start an AI-powered investigation.
      </p>
      <div className={styles.emptyExamples}>
        <p className={styles.examplesLabel}>Try an example:</p>
        <ul className={styles.examplesList}>
          <li>"BruteForceLoginAttempt on edge-sw-02 — 500 failed SSH attempts from 10.0.0.5"</li>
          <li>"TrafficSpike alert: edge-sw-02 showing 50,000 pps, baseline is 200 pps"</li>
          <li>"Prometheus fired HighThreatPayload — threat score 0.92 on core-router"</li>
        </ul>
      </div>
    </div>
  )
}

export default function ChatWindow({ conversationId }) {
  const bottomRef = useRef(null)
  const messages = conversationId === 'c-001' ? MOCK_MESSAGES : []

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  return (
    <div className={styles.window}>
      {messages.length === 0 ? (
        <EmptyState />
      ) : (
        <div className={styles.messages}>
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  )
}
