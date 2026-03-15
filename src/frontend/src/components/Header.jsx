import { AlertTriangle, Bell } from 'lucide-react'
import { MOCK_CONVERSATIONS } from '../mockData'
import styles from './Header.module.css'

const SEVERITY_LABEL = {
  critical: { label: 'Critical', color: 'var(--red)', bg: 'var(--red-bg)' },
  warning:  { label: 'Warning',  color: 'var(--yellow)', bg: 'var(--yellow-bg)' },
  info:     { label: 'Info',     color: 'var(--accent)', bg: 'var(--accent-glow)' },
}

export default function Header({ conversationId }) {
  const conv = MOCK_CONVERSATIONS.find((c) => c.id === conversationId)
  const severity = conv ? SEVERITY_LABEL[conv.severity] : null

  return (
    <header className={styles.header}>
      <div className={styles.left}>
        {conv ? (
          <>
            <span className={styles.title}>{conv.title}</span>
            {severity && (
              <span
                className={styles.badge}
                style={{ color: severity.color, background: severity.bg, borderColor: severity.color }}
              >
                <AlertTriangle size={10} />
                {severity.label}
              </span>
            )}
          </>
        ) : (
          <span className={styles.titleEmpty}>New Investigation</span>
        )}
      </div>
      <div className={styles.right}>
        <button className={styles.iconBtn} title="Notifications">
          <Bell size={15} />
        </button>
      </div>
    </header>
  )
}
