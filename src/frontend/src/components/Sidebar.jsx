import { useState, useEffect, useCallback } from 'react'
import { ShieldAlert, Plus, Circle, ChevronDown, Trash2, RefreshCw } from 'lucide-react'
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
  checking: 'var(--text-muted)',
}

// Health endpoints from docker-compose.yml port mappings
const SERVICE_CONFIG = [
  { label: 'AI Agent',       url: 'http://localhost:5050/health', detail: 'port 5050' },
  { label: 'Prometheus',     url: 'http://localhost:9090/-/healthy', detail: 'port 9090' },
  { label: 'AlertManager',   url: 'http://localhost:9093/-/healthy', detail: 'port 9093' },
  { label: 'Log Aggregator', url: 'http://localhost:8000/health',   detail: 'port 8000' },
  { label: 'MCP Server',     url: 'http://localhost:8080/sse',      detail: 'port 8080' },
]

const POLL_INTERVAL_MS = 30_000
const TIMEOUT_MS = 4_000

async function checkHealth(url) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  try {
    const res = await fetch(url, { signal: controller.signal, mode: 'no-cors' })
    clearTimeout(timer)
    // 'opaque' means server responded but CORS blocked reading — still means it's up
    return res.type === 'opaque' || res.ok ? 'online' : 'degraded'
  } catch (err) {
    clearTimeout(timer)
    return 'offline'
  }
}

function useServiceStatus() {
  const initial = SERVICE_CONFIG.map((s) => ({ ...s, status: 'checking' }))
  const [services, setServices] = useState(initial)
  const [lastChecked, setLastChecked] = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  const runChecks = useCallback(async () => {
    setRefreshing(true)
    const results = await Promise.all(
      SERVICE_CONFIG.map(async (svc) => ({
        ...svc,
        status: await checkHealth(svc.url),
      }))
    )
    setServices(results)
    setLastChecked(new Date())
    setRefreshing(false)
  }, [])

  useEffect(() => {
    runChecks()
    const id = setInterval(runChecks, POLL_INTERVAL_MS)
    return () => clearInterval(id)
  }, [runChecks])

  return { services, lastChecked, refreshing, refresh: runChecks }
}

function StatusDot({ status }) {
  return (
    <span
      className={`${styles.statusDot} ${status === 'checking' ? styles.statusDotPulse : ''}`}
      style={{ background: STATUS_COLOR[status] }}
      title={status}
    />
  )
}

export default function Sidebar({ conversations, activeId, onSelect, onNew, onDelete }) {
  const [statusExpanded, setStatusExpanded] = useState(true)
  const { services, lastChecked, refreshing, refresh } = useServiceStatus()

  const onlineCount = services.filter((s) => s.status === 'online').length

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
        {conversations.length === 0 && (
          <p className={styles.emptyNav}>No investigations yet</p>
        )}
        {conversations.map((conv) => (
          <div
            key={conv.id}
            className={`${styles.convItem} ${activeId === conv.id ? styles.convActive : ''}`}
            onClick={() => onSelect(conv.id)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && onSelect(conv.id)}
          >
            <Circle
              size={7}
              fill={SEVERITY_COLOR[conv.severity] ?? 'var(--accent)'}
              color={SEVERITY_COLOR[conv.severity] ?? 'var(--accent)'}
              className={styles.convDot}
            />
            <span className={styles.convTitle}>{conv.title}</span>
            <span className={styles.convTime}>{conv.timestamp}</span>
            <button
              className={styles.deleteBtn}
              onClick={(e) => {
                e.stopPropagation()
                onDelete(conv.id)
              }}
              title="Delete conversation"
              tabIndex={-1}
            >
              <Trash2 size={11} />
            </button>
          </div>
        ))}
      </nav>

      <div className={styles.spacer} />

      {/* System Status panel */}
      <div className={styles.statusPanel}>
        <button
          className={styles.statusHeader}
          onClick={() => setStatusExpanded((v) => !v)}
        >
          <span className={styles.sectionLabel} style={{ margin: 0 }}>
            System Status
          </span>
          <div className={styles.statusHeaderRight}>
            <span className={styles.statusCount}>
              {onlineCount}/{services.length}
            </span>
            <button
              className={`${styles.refreshBtn} ${refreshing ? styles.refreshBtnSpin : ''}`}
              onClick={(e) => { e.stopPropagation(); refresh() }}
              title={lastChecked ? `Last checked ${lastChecked.toLocaleTimeString()}` : 'Check now'}
              disabled={refreshing}
            >
              <RefreshCw size={11} />
            </button>
            <ChevronDown
              size={13}
              color="var(--text-muted)"
              style={{
                transform: statusExpanded ? 'rotate(0deg)' : 'rotate(-90deg)',
                transition: 'transform 0.2s',
              }}
            />
          </div>
        </button>
        {statusExpanded && (
          <ul className={styles.statusList}>
            {services.map((s) => (
              <li key={s.label} className={styles.statusItem}>
                <StatusDot status={s.status} />
                <span className={styles.statusLabel}>{s.label}</span>
                <span className={styles.statusDetail}>{s.detail}</span>
              </li>
            ))}
          </ul>
        )}
        {lastChecked && (
          <p className={styles.lastChecked}>
            Updated {lastChecked.toLocaleTimeString()}
          </p>
        )}
      </div>
    </aside>
  )
}
