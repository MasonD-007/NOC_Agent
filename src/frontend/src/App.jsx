import { useState } from 'react'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import ChatWindow from './components/ChatWindow'
import InputBar from './components/InputBar'
import styles from './App.module.css'

export default function App() {
  const [activeConversation, setActiveConversation] = useState('c-001')
  const [loading, setLoading] = useState(false)

  const handleNew = () => {
    setActiveConversation(null)
  }

  const handleSend = (text) => {
    // Wired up to backend later
    console.log('Send:', text)
    setLoading(true)
    setTimeout(() => setLoading(false), 2000)
  }

  return (
    <div className={styles.layout}>
      <Sidebar
        activeId={activeConversation}
        onSelect={setActiveConversation}
        onNew={handleNew}
      />
      <div className={styles.main}>
        <Header conversationId={activeConversation} />
        <ChatWindow conversationId={activeConversation} />
        <InputBar onSend={handleSend} loading={loading} />
      </div>
    </div>
  )
}
