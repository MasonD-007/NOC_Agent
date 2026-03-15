import { useState } from 'react'
import { ShieldAlert, Plus, Circle, ChevronDown } from 'lucide-react'
import { MOCK_CONVERSATIONS, SYSTEM_STATUS } from '../mockData'
import styles from './Sidebar.module.css'

const SEVERITY_COLOR = {
  critical: 'var(--red)',
  warning:  'var(--yellow)',
  info:     'var(--accent)',
}

const STATUS_COLOR = {
  online:   'var(--green)',
  degraded: 'var(--yellow)',
  offline:  'var(--red)',
}

function StatusDot({ status }) {
  return (
    <span
      className={styles.statusDot}
      style={{ background: STATUS_COLOR[status] }}
      title={status}
    />
  )
}

export default function Sidebar({ activeId, onSelect, onNew }) {
  const [statusExpanded, setStatusExpanded] = useState(true)

  return (
    <aside className={styles.sidebar}>
      {/* Brand */}
      <div className={styles.brand}>
        <div className={styles.brandIcon}>
          <ShieldAlert size={18} color="var(--accent)" />
        </div>
        <div className={styles.brandText}>
          <span className={styles.brandName}>NOC Agent</span>
          <span className={styles.brandSub}>AI-Powered Incident Response</span>
        </div>
      </div>

      {/* New chat button */}
      <div className={styles.newChatWrapper}>
        <button className={styles.newChatBtn} onClick={onNew}>
          <Plus size={14} />
          New Investigation
        </button>
      </div>

      {/* Conversations */}
      <nav className={styles.nav}>
        <p className={styles.sectionLabel}>Recent Incidents</p>
        {MOCK_CONVERSATIONS.map((conv) => (
          <button
            key={conv.id}
            className={`${styles.convItem} ${activeId === conv.id ? styles.convActive : ''}`}
            onClick={() => onSelect(conv.id)}
          >
            <Circle
              size={7}
              fill={SEVERITY_COLOR[conv.severity]}
              color={SEVERITY_COLOR[conv.severity]}
              className={styles.convDot}
            />
            <span className={styles.convTitle}>{conv.title}</span>
            <span className={styles.convTime}>{conv.timestamp}</span>
          </button>
        ))}
      </nav>

      <div className={styles.spacer} />

      {/* System Status panel */}
      <div className={styles.statusPanel}>
        <button
          className={styles.statusHeader}
          onClick={() => setStatusExpanded((v) => !v)}
        >
          <span className={styles.sectionLabel} style={{ margin: 0 }}>System Status</span>
          <ChevronDown
            size={13}
            color="var(--text-muted)"
            style={{
              transform: statusExpanded ? 'rotate(0deg)' : 'rotate(-90deg)',
              transition: 'transform 0.2s',
            }}
          />
        </button>
        {statusExpanded && (
          <ul className={styles.statusList}>
            {SYSTEM_STATUS.map((s) => (
              <li key={s.label} className={styles.statusItem}>
                <StatusDot status={s.status} />
                <span className={styles.statusLabel}>{s.label}</span>
                <span className={styles.statusDetail}>{s.detail}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  )
}
