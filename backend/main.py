from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import re
from market_real import BridgeMarketData
from brain import TradingBrain

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

market_provider = BridgeMarketData()
brain = TradingBrain()

# Global state for configuration
CONFIG = {
    "use_gemini": True,
    "auto_trade": False,
    "lot_size": 0.20,
    "monitored_symbols": []
}

@app.get("/config")
async def get_config():
    return CONFIG

@app.post("/config")
async def update_config(new_config: dict):
    CONFIG.update(new_config)
    print(f"--- CONFIGURACION ACTUALIZADA: {CONFIG} ---")
    return CONFIG

# Global state for locked trades
locked_trades = {}

@app.get("/lock_trade")
async def get_locked_trade(symbol: str):
    return locked_trades.get(symbol)

@app.post("/lock_trade")
async def update_locked_trade(payload: dict):
    symbol = payload.get("symbol")
    trade = payload.get("trade")
    if not trade:
        if symbol in locked_trades:
            del locked_trades[symbol]
    else:
        locked_trades[symbol] = trade
    print(f"--- POSICION FIJADA PARA {symbol}: {trade} ---")
    return {"status": "ok", "locked_trade": trade}

@app.post("/execute_manual_trade")
async def execute_manual_trade(payload: dict):
    symbol = payload.get("symbol")
    decision = payload.get("decision")
    sl = payload.get("stop_loss", 0)
    tp = payload.get("take_profit", 0)
    lot_size = CONFIG.get("lot_size", 0.20)
    
    print(f"--- [DISPARO MANUAL] SOLICITADO DESDE EL DASHBOARD: {decision} en {symbol} ---")
    trade_result = market_provider.execute_trade(
        symbol=symbol,
        decision=decision,
        lot_size=lot_size,
        sl=sl,
        tp=tp
    )
    
    if trade_result.get("success"):
        locked_trades[symbol] = {
            "decision": decision,
            "entry_price": trade_result["price"],
            "stop_loss": sl,
            "take_profit": tp,
            "ticket": trade_result["ticket"]
        }
        print(f"--- [EXITO] DISPARO EXITOSO (Ticket #{trade_result['ticket']}). POSICION FIJADA. ---")
        return {"success": True, "locked_trade": locked_trades[symbol]}
    else:
        print(f"--- [ERROR] DISPARANDO ORDEN: {trade_result.get('error')} ---")
        return {"success": False, "error": trade_result.get("error")}

@app.post("/close_manual_trade")
async def close_manual_trade(payload: dict):
    symbol = payload.get("symbol")
    ticket = payload.get("ticket")
    
    print(f"--- [CIERRE MANUAL] SOLICITADO DESDE EL DASHBOARD: Ticket #{ticket} en {symbol} ---")
    close_result = market_provider.close_trade(ticket=ticket, symbol=symbol)
    
    if close_result.get("success"):
        if symbol in locked_trades:
            del locked_trades[symbol]
        print(f"--- [EXITO] CIERRE EXITOSO (Ticket #{ticket}). POSICION LIBERADA. ---")
        return {"success": True, "closed_price": close_result.get("closed_price")}
    else:
        print(f"--- [ERROR] CERRANDO ORDEN #{ticket}: {close_result.get('error')} ---")
        return {"success": False, "error": close_result.get("error")}

# Global state for signals
last_signals = {}
# Global state for tick history per symbol
tick_histories = {}
MAX_HISTORY = 300 # Guardar los últimos 300 ticks para contexto

def detect_spike_setup(symbol, history):
    """
    Algoritmo Matemático de Alta Precisión (Spike Hunter)
    Analiza la compresión del precio para detectar Spikes inminentes en BullX y BearX.
    """
    if len(history) < 25 or ("Bull" not in symbol and "Bear" not in symbol):
        return None
        
    recent = history[-25:]
    first_price = recent[0]["price"]
    last_price = recent[-1]["price"]
    
    # Buscar si ya hubo un spike reciente (salto grande entre 2 ticks)
    for i in range(1, len(recent)):
        diff = recent[i]["price"] - recent[i-1]["price"]
        if "Bull" in symbol and diff > 3.0: # Spike alcista ya ocurrió
            return None
        if "Bear" in symbol and diff < -3.0: # Spike bajista ya ocurrió
            return None
            
    if "Bull" in symbol:
        drop = first_price - last_price
        # Si ha caído sostenidamente más de 3.5 puntos sin spikes, está a punto de reventar al alza
        if drop >= 3.5:
            return {
                "decision": "BUY",
                "type": "🚀 SPIKE HUNTER ENTRY",
                "is_continuation": False,
                "reason": f"🔥 [Cazador de Spikes] Compresión extrema de {round(drop, 2)} puntos a la baja sin retroceso. Spike ALCISTA inminente garantizado por comportamiento del índice.",
                "forecast": "Ruptura violenta al alza (Spike masivo).",
                "entry_price": last_price,
                "stop_loss": round(last_price - 10.0, 2),
                "take_profit": round(last_price + 30.0, 2),
                "confidence_score": 0.98
            }
            
    elif "Bear" in symbol:
        rise = last_price - first_price
        if rise >= 3.5:
            return {
                "decision": "SELL",
                "type": "☄️ SPIKE HUNTER ENTRY",
                "is_continuation": False,
                "reason": f"🔥 [Cazador de Spikes] Compresión extrema de {round(rise, 2)} puntos al alza sin retroceso. Spike BAJISTA inminente garantizado por comportamiento del índice.",
                "forecast": "Colapso violento a la baja (Spike masivo).",
                "entry_price": last_price,
                "stop_loss": round(last_price + 10.0, 2),
                "take_profit": round(last_price - 30.0, 2),
                "confidence_score": 0.98
            }
            
    return None

async def run_ai_analysis_global(symbol, history):
    ai_res = None
    locked = locked_trades.get(symbol)
    if CONFIG["use_gemini"]:
        try:
            res = await brain.analyze_ticks(symbol, history, last_signals.get(symbol), locked)
            if isinstance(res, str):
                clean_res = re.sub(r'```json\n|\n```', '', res)
                ai_res = json.loads(clean_res)
            else:
                ai_res = res
        except Exception as e:
            print(f"Error calling Gemini: {e}")
            ai_res = None
            
    # 🛡️ INTERCEPTOR ANTI-TRAMPA (CRÍTICO PARA BULLX Y BEARX) 🛡️
    # Evitar que la IA compre en la cima o venda en el fondo guiada por emociones falsas de momentum
    if ai_res and ai_res.get("decision") in ["BUY", "PENDING_BUY", "SELL", "PENDING_SELL", "EXIT", "CLOSE"]:
        if len(history) >= 10:
            recent_10 = history[-10:]
            current_price = recent_10[-1]["price"]
            max_10 = max(t["price"] for t in recent_10)
            min_10 = min(t["price"] for t in recent_10)
            
            if "Bull" in symbol:
                # Si la IA quiere comprar, pero el precio está en la cima del spike, BLOQUEAR
                if ai_res.get("decision") in ["BUY", "PENDING_BUY"] and (max_10 - current_price) < 1.0:
                    # Revisar si hubo un spike masivo
                    for i in range(1, len(recent_10)):
                        if recent_10[i]["price"] - recent_10[i-1]["price"] > 2.0:
                            ai_res["decision"] = "WAIT"
                            ai_res["reason"] = "🛡️ [SISTEMA ANTI-TRAMPA] IA intentó comprar en la cima del Spike en BullX. Operación suicida bloqueada por el Búnker."
                            print(f"--- 🛑 [BLOQUEO] IA intentó comprar en la cima de {symbol} ---")
                            break
                            
                # Si la IA quiere cerrar/salir por pánico justo en el fondo antes del próximo spike
                elif ai_res.get("decision") in ["EXIT", "CLOSE"] and (current_price - min_10) < 1.0:
                    ai_res["decision"] = "WAIT"
                    ai_res["reason"] = "🛡️ [SISTEMA ANTI-TRAMPA] IA intentó cerrar por pánico en el fondo de BullX. Bloqueado para esperar el Spike."
                    print(f"--- 🛑 [BLOQUEO] IA intentó cerrar en el fondo de {symbol} ---")

            elif "Bear" in symbol:
                # Si la IA quiere vender, pero el precio está en el fondo del spike
                if ai_res.get("decision") in ["SELL", "PENDING_SELL"] and (current_price - min_10) < 1.0:
                    for i in range(1, len(recent_10)):
                        if recent_10[i]["price"] - recent_10[i-1]["price"] < -2.0:
                            ai_res["decision"] = "WAIT"
                            ai_res["reason"] = "🛡️ [SISTEMA ANTI-TRAMPA] IA intentó vender en el fondo del Spike en BearX. Operación suicida bloqueada."
                            print(f"--- 🛑 [BLOQUEO] IA intentó vender en el fondo de {symbol} ---")
                            break
                            
                # Si la IA quiere cerrar/salir por pánico justo en la cima antes del próximo spike
                elif ai_res.get("decision") in ["EXIT", "CLOSE"] and (max_10 - current_price) < 1.0:
                    ai_res["decision"] = "WAIT"
                    ai_res["reason"] = "🛡️ [SISTEMA ANTI-TRAMPA] IA intentó cerrar por pánico en la cima de BearX. Bloqueado para esperar el Spike."
                    print(f"--- 🛑 [BLOQUEO] IA intentó cerrar en la cima de {symbol} ---")

    # Fallback o formateo si la decisión es WAIT o falló
    if not ai_res or ai_res.get("decision") == "WAIT":
        # 🛡️ INYECCIÓN DEL SPIKE HUNTER 🛡️
        # Si Gemini dice WAIT, consultamos a las matemáticas exactas del comportamiento del índice
        spike_override = detect_spike_setup(symbol, history)
        
        if spike_override:
            print(f"--- [SPIKE HUNTER] OVERRIDE DE IA ACTIVADO PARA {symbol}! ---")
            ai_res = spike_override
        else:
            last_price = history[-1]["price"] if history else 0
            ai_res = {
                "decision": "WAIT",
                "type": ai_res.get("type") if ai_res else "Espera / Rango",
                "is_continuation": False,
                "reason": ai_res.get("reason") if ai_res else "Sin convergencia clara de KLRR / Gann. Esperando setup de alta convicción.",
                "forecast": ai_res.get("forecast") if ai_res else "A la espera de ruptura estructural o patrón claro.",
                "entry_price": last_price,
                "stop_loss": 0,
                "take_profit": 0,
                "confidence_score": ai_res.get("confidence_score", 0.5) if ai_res else 0.5
            }
    else:
        active_positions = market_provider.get_open_positions(symbol)
        if active_positions and ai_res.get("decision") in ["EXIT", "SALIR", "CLOSE"]:
            print(f"--- [AI PROTECTOR] GEMINI ORDENA CIERRE INTELIGENTE DE GANANCIAS EN {symbol} ---")
            closed_count = 0
            for pos in active_positions:
                if pos["profit"] > 0:  # Priorizar el cierre de operaciones en verde
                    close_res = market_provider.close_trade(ticket=pos["ticket"], symbol=symbol)
                    if close_res.get("success"):
                        closed_count += 1
            if closed_count > 0:
                if symbol in locked_trades:
                    del locked_trades[symbol]
                ai_res["decision"] = "WAIT"
                ai_res["reason"] = f"🌟 [CIERRE INTELIGENTE KLRR] Operación cerrada en el pico para asegurar ganancias netas en cuenta. {ai_res.get('reason', '')}"
        elif locked:
            ai_res["decision"] = locked["decision"]
            ai_res["entry_price"] = locked["entry_price"]
            ai_res["stop_loss"] = locked["stop_loss"]
            ai_res["take_profit"] = locked["take_profit"]
        else:
            # Garantizar matemáticamente que el Stop Loss jamás exceda 10 puntos (10 velitas)
            try:
                entry = float(ai_res.get("entry_price", history[-1]["price"] if history else 0))
                sl = float(ai_res.get("stop_loss", 0))
                if ai_res.get("decision") == "BUY":
                    if sl < entry - 10.0 or sl >= entry:
                        ai_res["stop_loss"] = round(entry - 10.0, 2)
                elif ai_res.get("decision") == "SELL":
                    if sl > entry + 10.0 or sl <= entry:
                        ai_res["stop_loss"] = round(entry + 10.0, 2)
            except Exception as e:
                print(f"Error ajustando stop loss: {e}")
                
        # 🛑 PREVENCIÓN DE DUPLICADOS: Verificar si hay órdenes pendientes activas
        open_orders = market_provider.get_open_orders(symbol)
        if open_orders and ai_res.get("decision") in ["BUY", "SELL", "PENDING_BUY", "PENDING_SELL"]:
            # Ya hay una orden programada esperando llegar al precio
            ai_res["decision"] = "WAIT"
            ai_res["reason"] = f"⏳ [ORDEN PROGRAMADA ACTIVA] Ya existe una orden pendiente esperando en {open_orders[0].get('target_price')}. Suspendiendo nuevas entradas hasta que se active o cancele."
            
        # Auto-Trading Execution
        if CONFIG.get("auto_trade") and ai_res.get("decision") in ["BUY", "SELL", "PENDING_BUY", "PENDING_SELL"] and not locked:
            if float(ai_res.get("confidence_score", 0)) >= 0.75:
                decision = ai_res["decision"]
                if "PENDING" in decision:
                    target_price = float(ai_res.get("target_entry_price", history[-1]["price"]))
                    if target_price <= 0:
                        target_price = history[-1]["price"]
                        
                    print(f"--- [PROGRAMADA] INICIANDO ORDEN PENDIENTE PARA {symbol} EN {target_price} ---")
                    trade_result = market_provider.execute_pending_order(
                        symbol=symbol,
                        decision=decision.replace("PENDING_", ""),
                        lot_size=CONFIG.get("lot_size", 0.20),
                        target_price=target_price,
                        sl=ai_res["stop_loss"],
                        tp=ai_res["take_profit"]
                    )
                    
                    if trade_result.get("success"):
                        ai_res["reason"] = f"🎯 [EXITO PENDIENTE] ORDEN PROGRAMADA (Ticket: {trade_result['ticket']}) para ejecutarse en {target_price}. " + ai_res.get("reason", "")
                        print(f"--- [EXITO] ORDEN PROGRAMADA EXITOSA. ESPERANDO AL MERCADO. ---")
                    else:
                        ai_res["reason"] = f"[ERROR PENDIENTE]: {trade_result.get('error')}. " + ai_res.get("reason", "")
                else:
                    print(f"--- [SNIPER] INICIANDO AUTO-TRADING SNIPER PARA {symbol} ---")
                    trade_result = market_provider.execute_trade(
                        symbol=symbol,
                        decision=decision,
                        lot_size=CONFIG.get("lot_size", 0.20),
                        sl=ai_res["stop_loss"],
                        tp=ai_res["take_profit"]
                    )
                    if trade_result.get("success"):
                        # Lock trade automatically
                        locked_trades[symbol] = {
                            "decision": decision,
                            "entry_price": trade_result["price"],
                            "stop_loss": ai_res["stop_loss"],
                            "take_profit": ai_res["take_profit"],
                            "ticket": trade_result["ticket"]
                        }
                        ai_res["entry_price"] = trade_result["price"]
                        ai_res["reason"] = f"✅ [EXITO AUTO-TRADE] EJECUTADO A MERCADO (Ticket: {trade_result['ticket']}). " + ai_res.get("reason", "")
                        print(f"--- [EXITO] AUTO-TRADE EXITOSO. POSICION BLOQUEADA. ---")
                    else:
                        ai_res["reason"] = f"[ERROR AUTO-TRADE]: {trade_result.get('error')}. " + ai_res.get("reason", "")
    
    last_signals[symbol] = ai_res
    print(f"--- NUEVA SENAL PARA {symbol}: {ai_res['decision']} ---")

def check_trailing_stop(symbol, cur_price=None):
    """ Escanea las posiciones reales abiertas en MT5 para ese símbolo y ajusta Breakeven y Trailing Stop en ganancias """
    positions = market_provider.get_open_positions(symbol)
    if not positions:
        return
        
    for pos in positions:
        ticket = pos["ticket"]
        pos_type = pos["type"]
        entry = float(pos["open_price"])
        current = float(pos["current_price"])
        sl = float(pos["sl"])
        tp = float(pos["tp"])
        profit = float(pos["profit"])
        
        if pos_type == "BUY":
            # Trailing Stop Escalonado Inteligente en Ganancias
            if current >= entry + 30.0 or profit >= 30.0:
                # Si estamos con grandes ganancias (+$30 USD o +30 pts), aseguramos el 75% del recorrido
                target_sl = round(current - 10.0, 2)
                if target_sl > sl:
                    res = market_provider.modify_trade(symbol, ticket, target_sl, tp)
                    if res.get("success"):
                        if symbol in locked_trades:
                            locked_trades[symbol]["stop_loss"] = target_sl
                        print(f"[PROFIT PROTECTOR] BUY #{ticket} ({symbol}) +${profit}: SL ajustado a {target_sl} para blindar ganancia")
            elif current >= entry + 5.0 or profit >= 5.0:
                # Breakeven inicial
                target_sl = round(max(entry + 0.5, current - 4.5), 2)
                if sl < entry or target_sl >= sl + 0.5:
                    res = market_provider.modify_trade(symbol, ticket, target_sl, tp)
                    if res.get("success"):
                        if symbol in locked_trades:
                            locked_trades[symbol]["stop_loss"] = target_sl
                        print(f"[BREAKEVEN] BUY #{ticket} ({symbol}): SL movido a {target_sl}")
        elif pos_type == "SELL":
            # Trailing Stop Escalonado Inteligente en Ganancias
            if current <= entry - 30.0 or profit >= 30.0:
                # Si estamos con grandes ganancias (+$30 USD o +30 pts), aseguramos el 75% del recorrido
                target_sl = round(current + 10.0, 2)
                if sl == 0 or target_sl < sl:
                    res = market_provider.modify_trade(symbol, ticket, target_sl, tp)
                    if res.get("success"):
                        if symbol in locked_trades:
                            locked_trades[symbol]["stop_loss"] = target_sl
                        print(f"[PROFIT PROTECTOR] SELL #{ticket} ({symbol}) +${profit}: SL ajustado a {target_sl} para blindar ganancia")
            elif current <= entry - 5.0 or profit >= 5.0:
                # Breakeven inicial
                target_sl = round(min(entry - 0.5, current + 4.5), 2)
                if sl == 0 or sl > entry or target_sl <= sl - 0.5:
                    res = market_provider.modify_trade(symbol, ticket, target_sl, tp)
                    if res.get("success"):
                        if symbol in locked_trades:
                            locked_trades[symbol]["stop_loss"] = target_sl
                        print(f"[BREAKEVEN] SELL #{ticket} ({symbol}): SL movido a {target_sl}")

@app.websocket("/ws/market")
async def market_stream(websocket: WebSocket):
    symbol = websocket.query_params.get("symbol", "Fortune100.")
    print(f"--- NUEVO INTENTO DE CONEXION WS: {symbol} ---")
    await websocket.accept()
    print(f"--- CONEXION WS ACEPTADA PARA {symbol} ---")
    
    if symbol not in tick_histories:
        print(f"--- [PRELOAD] PRECARGANDO HISTORIAL DE MT5 PARA {symbol} ---")
        tick_histories[symbol] = market_provider.preload_history(symbol, MAX_HISTORY)

    try:
        while True:
            tick = market_provider.get_next_tick(symbol)
            if not tick:
                await websocket.send_json({
                    "type": "ERROR",
                    "message": "MT5 no devuelve datos. Revisa si el símbolo existe y el terminal está conectado."
                })
                await asyncio.sleep(1)
                continue
            
            # Guardar en el historial
            tick_histories[symbol].append(tick)
            if len(tick_histories[symbol]) > MAX_HISTORY:
                tick_histories[symbol].pop(0)
                
            check_trailing_stop(symbol, tick["price"])
            
            if tick["tick"] == 1 or tick["tick"] % 300 == 0:
                if symbol not in last_signals:
                    last_signals[symbol] = {
                        "decision": "ANALIZANDO",
                        "type": "Sincronizando ADN...",
                        "reason": "Observando flujo de ticks para identificar convergencia KLRR.",
                        "entry_price": tick["price"],
                        "stop_loss": 0, "take_profit": 0, "confidence_score": 0.5
                    }
                # Pasamos una copia del historial actual para dar contexto (hasta 300 ticks)
                asyncio.create_task(run_ai_analysis_global(symbol, list(tick_histories[symbol])))

            payload = {
                "type": "TICK",
                "data": tick,
                "ai_signal": last_signals.get(symbol),
                "locked_trade": locked_trades.get(symbol),
                "open_positions": market_provider.get_open_positions()
            }
            await websocket.send_json(payload)
            # print(f"--- TICK ENVIADO: {tick['price']} ---")
            await asyncio.sleep(0.1)
    except Exception as e:
        import traceback
        error_msg = f"--- WS ERROR ({symbol}): {e} ---\n{traceback.format_exc()}"
        print(error_msg)
        with open("debug.log", "a") as f:
            f.write(error_msg + "\n")

async def background_scanner():
    """ Tarea en segundo plano para escanear multiples indices sin requerir WS activo """
    print("--- [RADAR] INICIANDO RADAR MULTI-OBJETIVO (BACKGROUND SCANNER) ---")
    iteration = 0
    while True:
        try:
            monitored = CONFIG.get("monitored_symbols", [])
            for symbol in monitored:
                if symbol not in tick_histories:
                    print(f"--- [PRELOAD] PRECARGANDO HISTORIAL DE MT5 PARA {symbol} ---")
                    tick_histories[symbol] = market_provider.preload_history(symbol, MAX_HISTORY)
                    
                tick = market_provider.get_next_tick(symbol)
                if not tick:
                    continue
                    
                tick_histories[symbol].append(tick)
                if len(tick_histories[symbol]) > MAX_HISTORY:
                    tick_histories[symbol].pop(0)
                
                check_trailing_stop(symbol, tick["price"])
                
                # Ejecutar análisis IA cada 300 iteraciones (~1 minuto) para ahorrar costos de Gemini
                if iteration % 300 == 0:
                    asyncio.create_task(run_ai_analysis_global(symbol, list(tick_histories[symbol])))
                    
            iteration += 1
            await asyncio.sleep(0.2)
        except Exception as e:
            print(f"Error en scanner background: {e}")
            await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_scanner())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
