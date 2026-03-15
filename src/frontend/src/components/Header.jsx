import { AlertTriangle, Bell } from 'lucide-react'
import styles from './Header.module.css'

const SEVERITY_LABEL = {
  critical: { label: 'Critical', color: 'var(--red)',    bg: 'var(--red-bg)'       },
  warning:  { label: 'Warning',  color: 'var(--yellow)', bg: 'var(--yellow-bg)'    },
  info:     { label: 'Info',     color: 'var(--accent)', bg: 'var(--accent-glow)'  },
}

export default function Header({ conversation }) {
  const severity = conversation ? SEVERITY_LABEL[conversation.severity] : null

  return (
    <header className={styles.header}>
      <div className={styles.left}>
        {conversation ? (
          <>
            <span className={styles.title}>{conversation.title}</span>
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
