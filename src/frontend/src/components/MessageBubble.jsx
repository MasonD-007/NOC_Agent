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
    color: 'var(--yellow)',
    bg: 'var(--yellow-bg)',
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
    color: 'var(--green)',
    bg: 'var(--green-bg)',
  },
}

function resolveToolResult(result) {
  if (result === null) return { status: 'pending', outputText: '', device: null }
  if (typeof result === 'object') {
    const status = result.status === 'success' ? 'success' : 'error'
    const outputText = result.output ?? result.error ?? ''
    const device = result.device ?? null
    return { status, outputText, device }
  }
  // Plain string fallback
  const lower = String(result).toLowerCase()
  const status =
    lower.includes('permission denied') || lower.includes('error') || lower.includes('failed')
      ? 'error'
      : 'success'
  return { status, outputText: String(result), device: null }
}

function ToolCallCard({ tc }) {
  const { name, args, result } = tc
  const { status, outputText, device } = resolveToolResult(result)

  const displayArgs = Object.entries(args).filter(([k]) => k !== 'confirmed')

  return (
    <div className={styles.toolCard}>
      <div className={styles.toolCardHeader}>
        <span className={styles.toolName}>{name}</span>
        {device && <span className={styles.toolDevice}>{device}</span>}
        {status === 'pending' && <span className={styles.toolStatusPending}>running…</span>}
        {status === 'success' && <span className={`${styles.toolStatusBadge} ${styles.toolStatusSuccess}`}>✓ success</span>}
        {status === 'error' && <span className={`${styles.toolStatusBadge} ${styles.toolStatusError}`}>✗ error</span>}
      </div>

      {displayArgs.length > 0 && (
        <div className={styles.toolArgSection}>
          {displayArgs.map(([k, v]) => (
            <div key={k} className={styles.toolArgRow}>
              <span className={styles.toolArgKey}>{k}</span>
              <span className={styles.toolArgVal}>{String(v)}</span>
            </div>
          ))}
        </div>
      )}

      {outputText ? (
        <div className={`${styles.toolOutputSection} ${status === 'error' ? styles.toolOutputError : ''}`}>
          <pre className={styles.toolOutputPre}>{outputText}</pre>
        </div>
      ) : result !== null && (
        <div className={styles.toolOutputSection}>
          <span className={styles.toolOutputEmpty}>No output</span>
        </div>
      )}
    </div>
  )
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

  const isToolCalls = phase.name === 'investigate' && Array.isArray(phase.content)

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
        isToolCalls
          ? (
            <div className={styles.toolCallList}>
              {phase.content.map((tc, i) => (
                <ToolCallCard key={i} tc={tc} />
              ))}
            </div>
          )
          : Array.isArray(phase.content)
            ? <pre className={styles.phaseContent}>{JSON.stringify(phase.content, null, 2)}</pre>
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
