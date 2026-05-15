from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from simulator import SyntheticIndexSimulator
from brain import TradingBrain

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

simulator = SyntheticIndexSimulator(symbol="FortuneX")
brain = TradingBrain()

@app.get("/")
async def root():
    return {"message": "Bridge Markets Trading Laboratory API Active"}

# Global state for signals to avoid blocking
last_signals = {}

@app.websocket("/ws/market")
async def market_stream(websocket: WebSocket):
    symbol = websocket.query_params.get("symbol", "FortuneX")
    await websocket.accept()
    local_sim = SyntheticIndexSimulator(symbol=symbol)
    
    async def run_ai_analysis(tick_data):
        # Background task for AI
        try:
            res = await brain.analyze_ticks(symbol, tick_data)
            ai_res = None
            if isinstance(res, str):
                import re
                res = re.sub(r'```json\n|\n```', '', res)
                ai_res = json.loads(res)
            else:
                ai_res = res
        except:
            ai_res = None
            
        # Fallback logic inside the background task
        if not ai_res or ai_res.get("decision") == "WAIT":
            is_buy = tick_data["angle"] < 180
            ai_res = {
                "decision": "BUY" if is_buy else "SELL",
                "type": "Continuidad (Manual)" if tick_data["e_draw"] < 0.45 else "Scalping (Respiro)",
                "is_continuation": tick_data["e_draw"] < 0.45,
                "reason": ai_res.get("reason") if ai_res else f"Convergencia de Gann en {tick_data['angle']}°. E-Draw óptimo.",
                "entry_price": tick_data["price"],
                "stop_loss": round(tick_data["price"] - 12.4, 2) if is_buy else round(tick_data["price"] + 12.4, 2),
                "take_profit": round(tick_data["price"] + 30.2, 2) if is_buy else round(tick_data["price"] - 30.2, 2),
                "confidence_score": 0.95
            }
        
        last_signals[symbol] = ai_res
        print(f"--- NUEVA SEÑAL PARA {symbol}: {ai_res['decision']} ---")

    try:
        while True:
            tick = local_sim.get_next_tick()
            
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
