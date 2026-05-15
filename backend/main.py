from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
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

@app.get("/")
async def root():
    return {"message": "Bridge Markets Trading Laboratory API Active (REAL MARKET)"}

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

# Global state for signals to avoid blocking
last_signals = {}

@app.websocket("/ws/market")
async def market_stream(websocket: WebSocket):
    symbol = websocket.query_params.get("symbol", "Fortune100")
    await websocket.accept()
    
    async def run_ai_analysis(tick_data):
        # Background task for AI
        ai_res = None
        
        if CONFIG["use_gemini"]:
            try:
                res = await brain.analyze_ticks(symbol, tick_data)
                if isinstance(res, str):
                    import re
                    res = re.sub(r'```json\n|\n```', '', res)
                    ai_res = json.loads(res)
                else:
                    ai_res = res
            except Exception as e:
                print(f"Error calling Gemini: {e}")
                ai_res = None
        else:
            print(f"--- GEMINI IA DESACTIVADA (Ahorro de API) ---")
            
        # Fallback logic inside the background task (runs if AI is disabled or fails)
        if not ai_res or ai_res.get("decision") == "WAIT":
            is_buy = tick_data["angle"] < 180
            ai_res = {
                "decision": "BUY" if is_buy else "SELL",
                "type": "Continuidad (Manual)" if tick_data["e_draw"] < 0.45 else "Scalping (Respiro)",
                "is_continuation": tick_data["e_draw"] < 0.45,
                "reason": ai_res.get("reason") if ai_res else f"Algoritmo Matemático: Gann en {tick_data['angle']}°. (IA Apagada)",
                "entry_price": tick_data["price"],
                "stop_loss": round(tick_data["price"] - 12.4, 2) if is_buy else round(tick_data["price"] + 12.4, 2),
                "take_profit": round(tick_data["price"] + 30.2, 2) if is_buy else round(tick_data["price"] - 30.2, 2),
                "confidence_score": 0.85 if not ai_res else ai_res.get("confidence_score", 0.7)
            }
        
        last_signals[symbol] = ai_res
        print(f"--- NUEVA SEÑAL PARA {symbol}: {ai_res['decision']} ---")

    try:
        while True:
            tick = market_provider.get_next_tick(symbol)
            if not tick:
                await asyncio.sleep(1)
                continue
            
            # Trigger analysis at start (tick 1) and then every 50 ticks
            if tick["tick"] == 1 or tick["tick"] % 50 == 0:
                print(f"--- Iniciando análisis KLRR para {symbol} ---")
                
                # Immediate "Thinking" state if no signal yet
                if symbol not in last_signals:
                    last_signals[symbol] = {
                        "decision": "ANALIZANDO",
                        "type": "Sincronizando ADN...",
                        "reason": "Observando flujo de ticks para identificar convergencia KLRR.",
                        "entry_price": tick["price"],
                        "stop_loss": 0, "take_profit": 0, "confidence_score": 0.5
                    }
                
                asyncio.create_task(run_ai_analysis(tick))

            payload = {
                "type": "TICK",
                "data": tick,
                "ai_signal": last_signals.get(symbol)
            }
            
            await websocket.send_json(payload)
            await asyncio.sleep(0.1)
    except Exception as e:
        if "close message has been sent" not in str(e):
            print(f"WS Error for {symbol}: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
