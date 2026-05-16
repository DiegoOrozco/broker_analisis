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
    "use_gemini": True
}

@app.get("/config")
async def get_config():
    return CONFIG

@app.post("/config")
async def update_config(new_config: dict):
    CONFIG.update(new_config)
    print(f"--- CONFIGURACIÓN ACTUALIZADA: {CONFIG} ---")
    return CONFIG

# Global state for signals
last_signals = {}
# Global state for tick history per symbol
tick_histories = {}
MAX_HISTORY = 300 # Guardar los últimos 300 ticks para contexto

@app.websocket("/ws/market")
async def market_stream(websocket: WebSocket):
    symbol = websocket.query_params.get("symbol", "Fortune 100.")
    print(f"--- NUEVO INTENTO DE CONEXIÓN WS: {symbol} ---")
    await websocket.accept()
    print(f"--- CONEXIÓN WS ACEPTADA PARA {symbol} ---")
    
    if symbol not in tick_histories:
        tick_histories[symbol] = []

    async def run_ai_analysis(history):
        ai_res = None
        if CONFIG["use_gemini"]:
            try:
                res = await brain.analyze_ticks(symbol, history, last_signals.get(symbol))
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
                "forecast": ai_res.get("forecast") if ai_res else "A la espera de ruptura estructural o patrón claro del manual para proyectar el siguiente impulso.",
                "entry_price": last_price,
                "stop_loss": 0,
                "take_profit": 0,
                "confidence_score": ai_res.get("confidence_score", 0.5) if ai_res else 0.5
            }
        
        last_signals[symbol] = ai_res
        print(f"--- NUEVA SEÑAL PARA {symbol}: {ai_res['decision']} ---")

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
            
            if tick["tick"] == 1 or tick["tick"] % 50 == 0:
                if symbol not in last_signals:
                    last_signals[symbol] = {
                        "decision": "ANALIZANDO",
                        "type": "Sincronizando ADN...",
                        "reason": "Observando flujo de ticks para identificar convergencia KLRR.",
                        "entry_price": tick["price"],
                        "stop_loss": 0, "take_profit": 0, "confidence_score": 0.5
                    }
                # Pasamos una copia del historial actual para dar contexto (hasta 300 ticks)
                asyncio.create_task(run_ai_analysis(list(tick_histories[symbol])))

            payload = {
                "type": "TICK",
                "data": tick,
                "ai_signal": last_signals.get(symbol)
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
