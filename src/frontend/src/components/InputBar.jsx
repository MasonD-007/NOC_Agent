import { useState, useRef } from 'react'
import { Send, Loader2, Paperclip } from 'lucide-react'
import styles from './InputBar.module.css'

export default function InputBar({ onSend, loading = false }) {
  const [value, setValue] = useState('')
  const textareaRef = useRef(null)

  const handleInput = (e) => {
    setValue(e.target.value)
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = `${Math.min(el.scrollHeight, 180)}px`
    }
  }

  const handleSubmit = () => {
    const trimmed = value.trim()
    if (!trimmed || loading) return
    onSend?.(trimmed)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className={styles.wrapper}>
      <div className={`${styles.inputBox} ${loading ? styles.inputBoxLoading : ''}`}>
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          placeholder="Describe an alert or incident… (Shift+Enter for new line)"
          value={value}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={loading}
        />
        <div className={styles.actions}>
          <button
            className={styles.attachBtn}
            title="Attach alert JSON"
            disabled={loading}
          >
            <Paperclip size={15} />
          </button>
          <button
            className={`${styles.sendBtn} ${value.trim() && !loading ? styles.sendBtnActive : ''}`}
            onClick={handleSubmit}
            disabled={!value.trim() || loading}
            title="Send (Enter)"
          >
            {loading
              ? <Loader2 size={15} className={styles.spinner} />
              : <Send size={15} />
            }
          </button>
        </div>
      </div>
      <p className={styles.hint}>
        Press <kbd>Enter</kbd> to send · <kbd>Shift+Enter</kbd> for new line
      </p>
    </div>
  )
}
