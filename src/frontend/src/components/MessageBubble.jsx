import { useState } from 'react'
import Markdown from 'react-markdown'
import {
  User,
  Bot,
  ChevronDown,
  AlertTriangle,
  Search,
  Lightbulb,
  FileText,
} from 'lucide-react'
import styles from './MessageBubble.module.css'

const PHASE_META = {
  triage: {
    icon: AlertTriangle,
    label: 'Triage',
    color: 'var(--red)',
    bg: 'var(--red-bg)',
  },
  investigate: {
    icon: Search,
    label: 'Investigation',
    color: 'var(--cyan)',
    bg: 'var(--cyan-bg)',
  },
  recommend: {
    icon: Lightbulb,
    label: 'Recommendations',
    color: 'var(--yellow)',
    bg: 'var(--yellow-bg)',
  },
  report: {
    icon: FileText,
    label: 'Response',
    color: 'var(--purple)',
    bg: 'var(--purple-bg)',
  },
}

function PhaseBlock({ phase }) {
  const [open, setOpen] = useState(true)
  const meta = PHASE_META[phase.name] ?? {
    icon: FileText,
    label: phase.label,
    color: 'var(--accent)',
    bg: 'var(--accent-glow)',
  }
  const Icon = meta.icon

  // investigate phase shows raw tool I/O in monospace; all others render markdown
  const isRaw = phase.name === 'investigate'

  return (
    <div className={styles.phaseBlock} style={{ '--phase-color': meta.color, '--phase-bg': meta.bg }}>
      <button className={styles.phaseHeader} onClick={() => setOpen((v) => !v)}>
        <span className={styles.phaseIconWrap}>
          <Icon size={13} />
        </span>
        <span className={styles.phaseLabel}>{phase.label ?? meta.label}</span>
        <ChevronDown
          size={13}
          className={styles.phaseChevron}
          style={{ transform: open ? 'rotate(0deg)' : 'rotate(-90deg)' }}
        />
      </button>
      {open && (
        isRaw
          ? <pre className={styles.phaseContent}>{phase.content}</pre>
          : (
            <div className={styles.phaseMarkdown}>
              <Markdown
                components={{
                  code({ children }) {
                    return <code className={styles.inlineCode}>{children}</code>
                  },
                  pre({ children }) {
                    return <pre className={styles.codeBlock}>{children}</pre>
                  },
                }}
              >
                {phase.content}
              </Markdown>
            </div>
          )
      )}
    </div>
  )
}

function StreamingIndicator() {
  return (
    <div className={styles.streamingIndicator}>
      <span className={styles.streamingDot} />
      <span className={styles.streamingDot} />
      <span className={styles.streamingDot} />
    </div>
  )
}

export default function MessageBubble({ message }) {
  const isUser = message.role === 'user'
  const isStreaming = !isUser && message.streaming
  const hasPhases = !isUser && message.phases?.length > 0

  return (
    <div className={`${styles.row} ${isUser ? styles.rowUser : styles.rowAgent}`}>
      {/* Avatar */}
      <div className={`${styles.avatar} ${isUser ? styles.avatarUser : styles.avatarAgent}`}>
        {isUser ? <User size={14} /> : <Bot size={14} />}
      </div>

      <div className={styles.bubble}>
        {/* Header */}
        <div className={styles.header}>
          <span className={styles.author}>{isUser ? 'You' : 'NOC Agent'}</span>
          <span className={styles.timestamp}>{message.timestamp}</span>
        </div>

        {/* User message: plain text */}
        {isUser && (
          <p className={styles.userText}>{message.content}</p>
        )}

        {/* Agent message: phase blocks */}
        {!isUser && hasPhases && (
          <div className={styles.phases}>
            {message.phases.map((phase) => (
              <PhaseBlock key={phase.name} phase={phase} />
            ))}
            {isStreaming && <StreamingIndicator />}
          </div>
        )}

        {/* Agent message: thinking state (no phases yet) */}
        {!isUser && !hasPhases && isStreaming && (
          <div className={styles.thinkingBubble}>
            <StreamingIndicator />
            <span className={styles.thinkingLabel}>Thinking…</span>
          </div>
        )}
      </div>
    </div>
  )
}
