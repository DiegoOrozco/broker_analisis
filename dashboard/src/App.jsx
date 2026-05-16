import React, { useState, useEffect, useRef } from 'react'

function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [selectedSymbol, setSelectedSymbol] = useState('Fortune100.')
  const [ticks, setTicks] = useState([])
  const [currentTick, setCurrentTick] = useState(null)
  const [logs, setLogs] = useState([])
  const [isConnected, setIsConnected] = useState(false)
  const [lastSignal, setLastSignal] = useState(null)
  const [lockedTrade, setLockedTrade] = useState(null)
  const [useGemini, setUseGemini] = useState(true)
  const [autoTrade, setAutoTrade] = useState(false)
  const [monitoredSymbols, setMonitoredSymbols] = useState([])
  
  const ws = useRef(null)
  const API_BASE = "http://100.75.221.54:8000"
  const WS_BASE = "ws://100.75.221.54:8000"

  useEffect(() => {
    // Fetch initial config and locked trade
    fetch(`${API_BASE}/config`)
      .then(res => res.json())
      .then(data => {
        setUseGemini(data.use_gemini)
        setAutoTrade(data.auto_trade)
        setMonitoredSymbols(data.monitored_symbols || [])
      })
      .catch(err => console.error("Error fetching config:", err))
      
    fetch(`${API_BASE}/lock_trade?symbol=${encodeURIComponent(selectedSymbol)}`)
      .then(res => res.json())
      .then(data => setLockedTrade(data || null))
      .catch(err => console.error("Error fetching locked trade:", err))
  }, [selectedSymbol])

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

  const toggleAutoTrade = () => {
    const newValue = !autoTrade
    setAutoTrade(newValue)
    fetch(`${API_BASE}/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ auto_trade: newValue })
    }).then(() => {
      addLog(`🤖 AUTO-TRADING ${newValue ? 'ACTIVADO (Ejecución Directa MT5)' : 'DESACTIVADO (Modo Manual)'}`)
    })
  }

  const toggleMonitoredSymbol = (symbol) => {
    const newMonitored = monitoredSymbols.includes(symbol)
      ? monitoredSymbols.filter(s => s !== symbol)
      : [...monitoredSymbols, symbol]
    setMonitoredSymbols(newMonitored)
    fetch(`${API_BASE}/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ monitored_symbols: newMonitored })
    }).then(() => {
      addLog(`📡 RADAR ACTUALIZADO: Monitoreando [${newMonitored.join(', ')}]`)
    })
  }

  const lockCurrentTrade = () => {
    if (!lastSignal || lastSignal.decision === 'WAIT') return
    const tradeData = {
      decision: lastSignal.decision,
      entry_price: lastSignal.entry_price,
      stop_loss: lastSignal.stop_loss,
      take_profit: lastSignal.take_profit,
      symbol: selectedSymbol
    }
    fetch(`${API_BASE}/lock_trade`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol: selectedSymbol, trade: tradeData })
    }).then(res => res.json())
      .then(data => {
        setLockedTrade(data.locked_trade)
        addLog(`🔒 ENTRADA FIJADA: ${tradeData.decision} en ${tradeData.entry_price} (SL: ${tradeData.stop_loss}, TP: ${tradeData.take_profit})`)
      }).catch(err => console.error("Error locking trade:", err))
  }

  const unlockTrade = () => {
    fetch(`${API_BASE}/lock_trade`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol: selectedSymbol, trade: null })
    }).then(() => {
      setLockedTrade(null)
      addLog(`🔓 POSICIÓN LIBERADA PARA ${selectedSymbol}`)
    }).catch(err => console.error("Error unlocking trade:", err))
  }

  useEffect(() => {
    // Limpiar estado al cambiar de índice
    setTicks([])
    setCurrentTick(null)
    setLogs([])
    setLastSignal(null)

    const connect = () => {
      // Re-connect when symbol changes
      if (ws.current) {
        ws.current.onclose = null
        ws.current.close()
      }
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
          if (payload.locked_trade !== undefined) {
            setLockedTrade(payload.locked_trade || null)
          }
        } else if (payload.type === 'ERROR') {
          addLog(`ERROR MT5: ${payload.message}`)
        }
      }
      
      ws.current.onclose = () => {
        setIsConnected(false)
        setTimeout(connect, 3000)
      }
    }

    connect()
    return () => {
      if (ws.current) {
        ws.current.onclose = null
        ws.current.close()
      }
    }
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
          background: 'rgba(0, 255, 128, 0.1)',
          color: 'var(--success)',
          padding: '5px 12px',
          borderRadius: '20px',
          fontSize: '0.75rem',
          border: '1px solid var(--success)',
          fontWeight: 'bold'
        }}>
          REAL-TIME (MT5 BRIDGE MARKETS)
        </div>
      </header>

      <div className="card" style={{display: 'flex', flexWrap: 'wrap', gap: '15px', alignItems: 'center'}}>
        <span style={{color: 'var(--text-dim)'}}>Símbolos sugeridos:</span>
        {['Fortune100.', 'Fortune250.', 'FomoX111.', 'BullX400.', 'BearX400.'].map(s => (
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

           {lastSignal?.forecast && (
             <div style={{marginTop: '15px', padding: '15px', background: 'rgba(0, 191, 255, 0.1)', borderLeft: '3px solid #00bfff', borderRadius: '4px'}}>
               <strong style={{color: '#00bfff', display: 'block', marginBottom: '5px'}}>🔮 Proyección Proactiva:</strong>
               <span style={{color: 'var(--text-main)', fontSize: '0.95rem', lineHeight: '1.4'}}>{lastSignal.forecast}</span>
             </div>
           )}

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

           {lockedTrade ? (
             <div style={{marginTop: '25px', padding: '16px', background: 'rgba(38, 166, 154, 0.15)', border: '2px solid var(--success)', borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '15px'}}>
               <div>
                 <div style={{color: 'var(--success)', fontWeight: 'bold', fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '8px'}}>
                   🛡️ POSICIÓN FIJADA EN CURSO ({lockedTrade.decision})
                 </div>
                 <div style={{color: 'var(--text-dim)', fontSize: '0.95rem', marginTop: '6px'}}>
                   Entrada Confirmada: <strong style={{color: 'white'}}>{lockedTrade.entry_price}</strong> | SL: <strong style={{color: 'var(--danger)'}}>{lockedTrade.stop_loss}</strong> | TP: <strong style={{color: 'var(--success)'}}>{lockedTrade.take_profit}</strong>
                 </div>
               </div>
               <button 
                 onClick={unlockTrade}
                 style={{background: 'var(--danger)', color: 'white', border: 'none', padding: '10px 18px', borderRadius: '6px', fontWeight: 'bold', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.95rem'}}
               >
                 🔓 Cerrar / Liberar
               </button>
             </div>
           ) : (
             lastSignal && lastSignal.decision !== 'WAIT' && (
               <div style={{marginTop: '25px', padding: '16px', background: 'rgba(255, 255, 255, 0.05)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '15px'}}>
                 <div style={{color: 'var(--text-main)', fontSize: '0.95rem'}}>
                   ¿Entraste a esta señal en tu MT5? Fija el precio para seguimiento algorítmico en vivo:
                 </div>
                 <button 
                   onClick={lockCurrentTrade}
                   style={{background: 'var(--success)', color: 'white', border: 'none', padding: '10px 22px', borderRadius: '6px', fontWeight: 'bold', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.95rem', boxShadow: '0 0 15px rgba(38, 166, 154, 0.4)'}}
                 >
                   ✅ Confirmar Entrada en {lastSignal.entry_price}
                 </button>
               </div>
             )
           )}
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

           <div className="card" style={{padding: '15px', marginTop: '15px', border: autoTrade ? '1px solid var(--success)' : 'none'}}>
              <h4 style={{fontSize: '0.8rem', marginBottom: '10px'}}>AUTO-TRADING MT5</h4>
              <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}>
                <span style={{fontSize: '0.7rem', color: autoTrade ? 'var(--success)' : 'var(--text-dim)', fontWeight: autoTrade ? 'bold' : 'normal'}}>
                  {autoTrade ? 'IA DISPARANDO' : 'MODO MANUAL'}
                </span>
                <button 
                  onClick={toggleAutoTrade}
                  style={{
                    width: '40px',
                    height: '20px',
                    borderRadius: '10px',
                    background: autoTrade ? 'var(--success)' : 'var(--border)',
                    border: 'none',
                    position: 'relative',
                    cursor: 'pointer',
                    transition: 'all 0.3s',
                    boxShadow: autoTrade ? '0 0 10px rgba(38, 166, 154, 0.5)' : 'none'
                  }}
                >
                  <div style={{
                    width: '16px',
                    height: '16px',
                    borderRadius: '50%',
                    background: 'white',
                    position: 'absolute',
                    top: '2px',
                    left: autoTrade ? '22px' : '2px',
                    transition: 'all 0.3s'
                  }} />
                </button>
              </div>
           </div>

           <div className="card" style={{padding: '15px', marginTop: '15px'}}>
              <h4 style={{fontSize: '0.8rem', marginBottom: '10px'}}>📡 RADAR (SCANNER 24/7)</h4>
              <p style={{fontSize: '0.7rem', color: 'var(--text-dim)', marginBottom: '10px'}}>
                Selecciona los índices que la IA monitoreará en segundo plano, sin importar cuál estés viendo en pantalla.
              </p>
              <div style={{display: 'flex', flexDirection: 'column', gap: '8px'}}>
                {['Fortune100.', 'Fortune250.', 'BullX400.', 'BearX400.', 'VorteX75.', 'FomoX111.'].map(sym => (
                  <label key={sym} style={{display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', cursor: 'pointer', color: monitoredSymbols.includes(sym) ? 'var(--accent-primary)' : 'var(--text-main)'}}>
                    <input 
                      type="checkbox" 
                      checked={monitoredSymbols.includes(sym)}
                      onChange={() => toggleMonitoredSymbol(sym)}
                      style={{accentColor: 'var(--accent-primary)'}}
                    />
                    {sym}
                  </label>
                ))}
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
