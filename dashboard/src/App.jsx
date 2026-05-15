import React, { useState, useEffect, useRef } from 'react'

function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [selectedSymbol, setSelectedSymbol] = useState('FortuneX')
  const [ticks, setTicks] = useState([])
  const [currentTick, setCurrentTick] = useState(null)
  const [logs, setLogs] = useState([])
  const [isConnected, setIsConnected] = useState(false)
  const [lastSignal, setLastSignal] = useState(null)
  const [useGemini, setUseGemini] = useState(true)
  
  const ws = useRef(null)
  const API_BASE = "http://100.75.221.54:8000"
  const WS_BASE = "ws://100.75.221.54:8000"

  useEffect(() => {
    // Fetch initial config
    fetch(`${API_BASE}/config`)
      .then(res => res.json())
      .then(data => setUseGemini(data.use_gemini))
      .catch(err => console.error("Error fetching config:", err))
  }, [])

  const toggleGemini = () => {
    const newValue = !useGemini
    setUseGemini(newValue)
    fetch(`${API_BASE}/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ use_gemini: newValue })
    }).then(() => {
      addLog(`IA Gemini ${newValue ? 'ACTIVADA' : 'DESACTIVADA (Modo Ahorro)'}`)
    })
  }

  useEffect(() => {
    const connect = () => {
      // Re-connect when symbol changes
      if (ws.current) ws.current.close()
      
      ws.current = new WebSocket(`${WS_BASE}/ws/market?symbol=${encodeURIComponent(selectedSymbol)}`)
      
      ws.current.onopen = () => {
        setIsConnected(true)
        addLog(`Conectado al núcleo Windows: Analizando ${selectedSymbol}`)
      }
// ... (rest of the useEffect logic remains mostly same but I need to make sure I don't break the nesting)
      
      ws.current.onmessage = (event) => {
        const payload = JSON.parse(event.data)
        if (payload.type === 'TICK') {
          const newTick = payload.data
          setCurrentTick(newTick)
          setTicks(prev => [...prev.slice(-30), newTick])
          
          if (payload.ai_signal) {
            setLastSignal(payload.ai_signal)
            addLog(`NUEVA SEÑAL: ${payload.ai_signal.decision} - ${payload.ai_signal.reason}`)
          }
        }
      }
      
      ws.current.onclose = () => {
        setIsConnected(false)
        setTimeout(connect, 3000)
      }
    }

    connect()
    return () => ws.current?.close()
  }, [selectedSymbol])

  const addLog = (msg) => {
    setLogs(prev => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev.slice(0, 50)])
  }

  const getAngleColor = (angle) => {
    if (angle >= 90 && angle <= 180) return 'var(--success)'
    if (angle >= 270) return 'var(--danger)'
    return 'var(--accent-primary)'
  }

  const renderDashboard = () => (
    <>
      <header style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px'}}>
        <h1>{selectedSymbol} <span style={{fontSize: '1rem', color: 'var(--text-dim)', fontWeight: 400}}>Nanosegmento</span></h1>
        <div className="metric-value">
          ${currentTick?.price || '0.00'}
        </div>
      </header>

      <div className="card" style={{height: '400px', display: 'flex', flexDirection: 'column'}}>
         <h3>Firma Algorítmica (Ticks)</h3>
         <div className="price-chart" style={{alignItems: 'center'}}>
            {ticks.map((t, i) => (
              <div 
                key={i} 
                className="chart-bar" 
                style={{ 
                  height: `${20 + (t.price % 50) * 4}px`,
                  background: getAngleColor(t.angle),
                  opacity: 0.8
                }}
              />
            ))}
         </div>
      </div>

      <div className="metric-grid">
         <div className="card">
            <h3>Ángulo de Gann</h3>
            <div className="metric-value" style={{color: getAngleColor(currentTick?.angle)}}>
              {currentTick?.angle || 0}°
            </div>
            <p style={{fontSize: '0.8rem', color: 'var(--text-dim)'}}>
              {currentTick?.angle < 90 ? 'Acumulación' : currentTick?.angle < 180 ? 'Liberación' : currentTick?.angle < 270 ? 'Compresión' : 'Redistribución'}
            </p>
         </div>
         <div className="card">
            <h3>E-Draw (Energía)</h3>
            <div className="metric-value">
              {currentTick?.e_draw || 0}
            </div>
            <div style={{height: '4px', background: 'var(--border)', borderRadius: '2px', marginTop: '10px'}}>
              <div style={{
                height: '100%', 
                width: `${(currentTick?.e_draw || 0) * 100}%`, 
                background: (currentTick?.e_draw || 0) > 0.6 ? 'var(--danger)' : 'var(--success)',
              }} />
            </div>
         </div>
      </div>
    </>
  )

  const renderAnalyzer = () => (
    <div style={{animation: 'fadeIn 0.5s'}}>
      <header style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px'}}>
        <h1>KLRR Analyzer <span style={{fontSize: '1rem', color: 'var(--text-dim)'}}>Señales de Entrada/Salida</span></h1>
        <div style={{
          background: 'rgba(255, 193, 7, 0.1)',
          color: '#ffc107',
          padding: '5px 12px',
          borderRadius: '20px',
          fontSize: '0.75rem',
          border: '1px solid #ffc107',
          fontWeight: 'bold'
        }}>
          ⚠️ MODO LABORATORIO (SIMULADO)
        </div>
      </header>

      <div className="card" style={{display: 'flex', flexWrap: 'wrap', gap: '15px', alignItems: 'center'}}>
        <span style={{color: 'var(--text-dim)'}}>Símbolos sugeridos:</span>
        {['Fortune 100.', 'Fortune 250.', 'Fortune 1000.', 'FortuneX200.', 'Volatility 75 Index'].map(s => (
          <button 
            key={s}
            onClick={() => setSelectedSymbol(s)}
            style={{
              padding: '8px 15px',
              background: selectedSymbol === s ? 'var(--accent-primary)' : 'var(--bg-card)',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              color: selectedSymbol === s ? 'black' : 'white',
              cursor: 'pointer',
              fontSize: '0.85rem'
            }}
          >
            {s}
          </button>
        ))}
        <div style={{display: 'flex', gap: '10px', marginLeft: 'auto', alignItems: 'center'}}>
           <span style={{color: 'var(--text-dim)', fontSize: '0.8rem'}}>OTRO:</span>
           <input 
             type="text" 
             placeholder="Ej: BullX400"
             onKeyDown={(e) => {
               if (e.key === 'Enter') setSelectedSymbol(e.target.value)
             }}
             style={{
               background: 'var(--bg-dark)',
               border: '1px solid var(--border)',
               borderRadius: '6px',
               color: 'white',
               padding: '8px',
               width: '120px'
             }}
           />
        </div>
      </div>

      <div className="metric-grid" style={{marginTop: '20px'}}>
        <div className="card" style={{gridColumn: 'span 2', borderLeft: `4px solid ${lastSignal?.decision === 'BUY' ? 'var(--success)' : lastSignal?.decision === 'SELL' ? 'var(--danger)' : 'var(--warning)'}`}}>
           <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start'}}>
              <div>
                <h2 style={{color: 'var(--text-dim)', fontSize: '0.9rem', textTransform: 'uppercase'}}>Sugerencia IA</h2>
                <div className="metric-value" style={{fontSize: '2.5rem', marginTop: '10px'}}>
                  {lastSignal?.decision || 'ESPERANDO CONVERGENCIA...'}
                </div>
              </div>
              <div className="status-badge live" style={{background: 'rgba(255, 204, 0, 0.1)', color: 'var(--warning)', borderColor: 'var(--warning)'}}>
                {lastSignal?.type || 'Analizando Flujo'}
              </div>
           </div>
           
           <p style={{marginTop: '20px', color: 'var(--text-main)', fontSize: '1.1rem', lineHeight: '1.5'}}>
              {lastSignal?.reason || 'El sistema está monitoreando los ciclos de Gann y niveles Wyckoff para identificar el próximo KLRR.'}
           </p>

           <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '20px', marginTop: '30px', borderTop: '1px solid var(--border)', paddingTop: '20px'}}>
              <div>
                <span style={{color: 'var(--text-dim)', fontSize: '0.8rem'}}>PUNTO DE ENTRADA</span>
                <div style={{fontFamily: 'JetBrains Mono', fontSize: '1.2rem', color: 'var(--success)'}}>{lastSignal?.entry_price || '---'}</div>
              </div>
              <div>
                <span style={{color: 'var(--text-dim)', fontSize: '0.8rem'}}>STOP LOSS</span>
                <div style={{fontFamily: 'JetBrains Mono', fontSize: '1.2rem', color: 'var(--danger)'}}>{lastSignal?.stop_loss || '---'}</div>
              </div>
              <div>
                <span style={{color: 'var(--text-dim)', fontSize: '0.8rem'}}>TAKE PROFIT</span>
                <div style={{fontFamily: 'JetBrains Mono', fontSize: '1.2rem'}}>{lastSignal?.take_profit || '---'}</div>
              </div>
           </div>
        </div>

        <div className="card">
           <h3>Probabilidad</h3>
           <div className="metric-value" style={{fontSize: '3rem'}}>
              {Math.round((lastSignal?.confidence_score || 0.66) * 100)}%
           </div>
           <p style={{color: 'var(--text-dim)'}}>Determinismo detectado vs Ruido inductivo.</p>
        </div>

        <div className="card">
           <h3>Tipo de Operación</h3>
           <div className="metric-value" style={{color: 'var(--warning)'}}>
              {lastSignal?.decision === 'WAIT' ? 'MONITOREO' : (lastSignal?.is_continuation ? 'CONTINUIDAD' : 'SCALPING')}
           </div>
           <p style={{color: 'var(--text-dim)'}}>
              {lastSignal?.is_continuation ? 'Tendencia sólida detectada.' : 'Movimiento de respiro/retest.'}
           </p>
        </div>
      </div>
    </div>
  )

  return (
    <div className="dashboard-container">
      <aside>
        <div className="sidebar-header">
          <h2 className="accent-text">BRIDGE LAB</h2>
          <p style={{fontSize: '0.7rem', color: 'var(--text-dim)'}}>ESTRATEGIA PROFESIONAL</p>
        </div>
        
        <div className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveTab('dashboard')}>
          Visualizador Real-Time
        </div>
        <div className={`nav-item ${activeTab === 'analyzer' ? 'active' : ''}`} onClick={() => setActiveTab('analyzer')}>
          KLRR Analyzer (Señales)
        </div>
        <div className="nav-item">Manual Ground Truth</div>
        
        <div style={{padding: '30px'}}>
           <div className="card" style={{padding: '15px'}}>
              <h4 style={{fontSize: '0.8rem', marginBottom: '10px'}}>CONEXIÓN</h4>
              <div className={`status-badge ${isConnected ? 'live' : ''}`}>
                {isConnected ? 'SISTEMA ACTIVO' : 'OFFLINE'}
              </div>
           </div>

           <div className="card" style={{padding: '15px', marginTop: '15px'}}>
              <h4 style={{fontSize: '0.8rem', marginBottom: '10px'}}>IA GEMINI</h4>
              <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}>
                <span style={{fontSize: '0.7rem', color: useGemini ? 'var(--success)' : 'var(--text-dim)'}}>
                  {useGemini ? 'ACTIVA' : 'MODO AHORRO'}
                </span>
                <button 
                  onClick={toggleGemini}
                  style={{
                    width: '40px',
                    height: '20px',
                    borderRadius: '10px',
                    background: useGemini ? 'var(--accent-primary)' : 'var(--border)',
                    border: 'none',
                    position: 'relative',
                    cursor: 'pointer',
                    transition: 'all 0.3s'
                  }}
                >
                  <div style={{
                    width: '16px',
                    height: '16px',
                    borderRadius: '50%',
                    background: 'white',
                    position: 'absolute',
                    top: '2px',
                    left: useGemini ? '22px' : '2px',
                    transition: 'all 0.3s'
                  }} />
                </button>
              </div>
           </div>
        </div>
      </aside>

      <main style={{padding: '30px'}}>
        {activeTab === 'dashboard' ? renderDashboard() : renderAnalyzer()}
      </main>

      <aside style={{borderLeft: '1px solid var(--border)'}}>
        <div style={{padding: '20px', height: '100%'}}>
          <h3>Ground Truth Logs</h3>
          <div className="log-panel">
            {logs.map((log, i) => (
              <div key={i} className="log-entry">{log}</div>
            ))}
          </div>
        </div>
      </aside>
    </div>
  )
}

export default App
