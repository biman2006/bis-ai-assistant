import { useEffect, useRef, useState } from 'react'
import { ArrowUp, CircleHelp, FileText, Languages, RotateCcw, ShieldCheck } from 'lucide-react'
import ChatMessage from './components/ChatMessage'
import { getHealth, sendChat } from './services/api'

function App() {
  const [messages, setMessages] = useState([])
  const [query, setQuery] = useState('')
  const [language, setLanguage] = useState('en')
  const [sessionId, setSessionId] = useState(() => localStorage.getItem('bis-session-id') || '')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [isOnline, setIsOnline] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    getHealth().then(() => setIsOnline(true)).catch(() => setIsOnline(false))
  }, [])

  const submitQuery = async (event, suggestedQuery = null) => {
    event?.preventDefault()
    const text = (suggestedQuery ?? query).trim()
    if (!text || isLoading) return

    setError('')
    setQuery('')
    setMessages((current) => [...current, { role: 'user', content: text, timestamp: new Date().toISOString() }])
    setIsLoading(true)

    try {
      const response = await sendChat({ query: text, session_id: sessionId || undefined, language })
      if (response.session_id) {
        setSessionId(response.session_id)
        localStorage.setItem('bis-session-id', response.session_id)
      }
      setMessages((current) => [...current, {
        role: 'assistant',
        content: response.answer,
        timestamp: new Date().toISOString(),
        ...response,
      }])
      setIsOnline(true)
    } catch (requestError) {
      setError(requestError.message || 'The assistant could not be reached.')
      setIsOnline(false)
    } finally {
      setIsLoading(false)
      inputRef.current?.focus()
    }
  }

  const startNewChat = () => {
    setMessages([])
    setError('')
    setSessionId('')
    localStorage.removeItem('bis-session-id')
    inputRef.current?.focus()
  }

  const suggestions = [
    'How do I apply for a BIS licence?',
    'Is BIS certification mandatory for electrical products?',
    'What is a Quality Control Order (QCO)?',
  ]

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-logo">
          <div className="header-logo-badge">BIS</div>
          <div><div className="header-title">BIS AI Assistant</div><div className="header-subtitle">Indian Standards and certification guidance</div></div>
        </div>
        <div className="header-spacer" />
        <div className="health-badge" title={isOnline ? 'Backend connected' : 'Backend unavailable'}><span className={`health-dot${isOnline ? '' : ' offline'}`} />{isOnline ? 'Online' : 'Offline'}</div>
        <button className="nav-btn" type="button" onClick={startNewChat} title="Start a new conversation"><RotateCcw size={14} /> New chat</button>
      </header>

      <main className="app-main">
        <section className="chat-layout">
          {messages.length === 0 ? (
            <div className="welcome-screen">
              <div className="welcome-hero">
                <div className="welcome-icon"><ShieldCheck size={30} /></div>
                <h1 className="welcome-title">Ask about BIS standards</h1>
                <p className="welcome-subtitle">Get grounded guidance on Indian Standards, certification, licences, QCOs, and the BIS mark.</p>
                <div className="welcome-disclaimer"><CircleHelp size={13} /> Verify requirements against the latest official notification.</div>
              </div>
              <div className="suggested-questions"><div className="suggested-title">Try a question</div><div className="suggested-chips">{suggestions.map((suggestion) => <button key={suggestion} className="suggested-chip" type="button" onClick={(event) => submitQuery(event, suggestion)}>{suggestion}</button>)}</div></div>
            </div>
          ) : (
            <div className="chat-messages">
              {messages.map((message, index) => <ChatMessage key={`${message.role}-${index}`} message={message} />)}
              {isLoading && <div className="chat-message assistant"><div className="message-avatar avatar-assistant">BIS</div><div className="message-content-wrapper"><div className="message-bubble typing-indicator"><span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" /></div></div></div>}
            </div>
          )}

          {error && <div className="alert alert-error" role="alert">{error}</div>}
          <div className="chat-input-area"><div className="chat-input-wrapper"><form className="chat-input-form" onSubmit={submitQuery}><textarea ref={inputRef} className="chat-input-box" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); submitQuery(event) } }} placeholder="Ask a question about BIS..." rows="1" maxLength="2000" disabled={isLoading} /><button className="send-btn" type="submit" disabled={!query.trim() || isLoading} aria-label="Send question" title="Send question"><ArrowUp size={19} /></button></form><div className="chat-input-footer"><span className="input-hint">Enter to send, Shift+Enter for a new line</span><label className="lang-selector"><Languages size={13} /><span className="sr-only">Response language</span><select className="lang-select" value={language} onChange={(event) => setLanguage(event.target.value)}><option value="en">English</option><option value="hi">Hindi</option><option value="bn">Bengali</option></select></label></div></div></div>
          <div className="disclaimer-bar"><FileText size={11} /> Answers use the indexed BIS knowledge base and include official sources when available.</div>
        </section>
      </main>
    </div>
  )
}

export default App
