import { useState } from 'react'
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
    label: 'Incident Report',
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

  return (
    <div className={styles.phaseBlock} style={{ '--phase-color': meta.color, '--phase-bg': meta.bg }}>
      <button className={styles.phaseHeader} onClick={() => setOpen((v) => !v)}>
        <span className={styles.phaseIconWrap}>
          <Icon size={13} />
        </span>
        <span className={styles.phaseLabel}>{meta.label}</span>
        <ChevronDown
          size={13}
          className={styles.phaseChevron}
          style={{ transform: open ? 'rotate(0deg)' : 'rotate(-90deg)' }}
        />
      </button>
      {open && (
        <pre className={styles.phaseContent}>{phase.content}</pre>
      )}
    </div>
  )
}

export default function MessageBubble({ message }) {
  const isUser = message.role === 'user'

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
        {!isUser && message.phases && (
          <div className={styles.phases}>
            {message.phases.map((phase) => (
              <PhaseBlock key={phase.name} phase={phase} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
