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
            
    # Fallback o formateo si la decisión es WAIT o falló
    if not ai_res or ai_res.get("decision") == "WAIT":
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
        if locked:
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
                
        # Auto-Trading Execution
        if CONFIG.get("auto_trade") and ai_res.get("decision") in ["BUY", "SELL"] and not locked:
            if float(ai_res.get("confidence_score", 0)) >= 0.75:
                print(f"--- [SNIPER] INICIANDO AUTO-TRADING SNIPER PARA {symbol} ---")
                trade_result = market_provider.execute_trade(
                    symbol=symbol,
                    decision=ai_res["decision"],
                    lot_size=CONFIG.get("lot_size", 0.20),
                    sl=ai_res["stop_loss"],
                    tp=ai_res["take_profit"]
                )
                if trade_result.get("success"):
                    # Lock trade automatically
                    locked_trades[symbol] = {
                        "decision": ai_res["decision"],
                        "entry_price": trade_result["price"],
                        "stop_loss": ai_res["stop_loss"],
                        "take_profit": ai_res["take_profit"],
                        "ticket": trade_result["ticket"]
                    }
                    ai_res["entry_price"] = trade_result["price"]
                    ai_res["reason"] = f"[EXITO AUTO-TRADE] EJECUTADO (Ticket: {trade_result['ticket']}). " + ai_res.get("reason", "")
                    print(f"--- [EXITO] AUTO-TRADE EXITOSO. POSICION BLOQUEADA. ---")
                else:
                    ai_res["reason"] = f"[ERROR AUTO-TRADE]: {trade_result.get('error')}. " + ai_res.get("reason", "")
    
    last_signals[symbol] = ai_res
    print(f"--- NUEVA SENAL PARA {symbol}: {ai_res['decision']} ---")

def check_trailing_stop(symbol, cur_price):
    """ Mueve el Stop Loss a Breakeven y lo persigue (Trailing Stop) en MT5 """
    if symbol in locked_trades and "ticket" in locked_trades[symbol]:
        trade = locked_trades[symbol]
        decision = trade["decision"]
        entry = float(trade["entry_price"])
        sl = float(trade["stop_loss"])
        tp = float(trade["take_profit"])
        ticket = trade["ticket"]
        
        if decision == "BUY":
            if cur_price >= entry + 5.0:
                new_sl = round(max(sl, entry + 0.5, cur_price - 4.5), 2)
                if new_sl > sl:
                    res = market_provider.modify_trade(symbol, ticket, new_sl, tp)
                    if res.get("success"):
                        locked_trades[symbol]["stop_loss"] = new_sl
                        print(f"[TRAILING] TRAILING STOP AJUSTADO EN MT5 ({symbol}): {sl} -> {new_sl}")
        elif decision == "SELL":
            if cur_price <= entry - 5.0:
                new_sl = round(min(sl if sl > 0 else entry + 10, entry - 0.5, cur_price + 4.5), 2)
                if new_sl < sl or sl == 0:
                    res = market_provider.modify_trade(symbol, ticket, new_sl, tp)
                    if res.get("success"):
                        locked_trades[symbol]["stop_loss"] = new_sl
                        print(f"[TRAILING] TRAILING STOP AJUSTADO EN MT5 ({symbol}): {sl} -> {new_sl}")

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
