import MetaTrader5 as mt5
import os
import time
from dotenv import load_dotenv

# Logging a archivo para depuración extrema
def log_debug(msg):
    with open("debug.log", "a") as f:
        f.write(f"[{time.ctime()}] {msg}\n")
    print(msg)

load_dotenv()

class BridgeMarketData:
    """
    Connects to Bridge Markets MetaTrader 5 and provides real-time tick data.
    """
    def __init__(self):
        self.login = int(os.getenv("MT5_LOGIN", 0))
        self.password = os.getenv("MT5_PASSWORD", "")
        self.server = os.getenv("MT5_SERVER", "BridgeMarkets-Server")
        self.connected = False
        self.tick_counts = {} # Track ticks per symbol for Gann angles
        
    def connect(self):
        # Intentar conexión al terminal abierto
        # A veces initialize devuelve False con error de auth, pero login() funciona después
        mt5.initialize() 
        
        # Login con el servidor correcto
        authorized = mt5.login(self.login, password=self.password, server="BridgeMarkets-MT5")
        if authorized:
            log_debug(f"--- CONECTADO A BRIDGE MARKETS MT5 (Acc: {self.login}) ---")
            self.connected = True
            return True
        else:
            log_debug(f"--- FALLO LOGIN MT5 (Acc: {self.login}, Serv: BridgeMarkets-MT5) ---")
            log_debug(f"Error code = {mt5.last_error()}")
            # Si falla el login, cerramos para no dejar basura
            mt5.shutdown()
            return False

    def get_next_tick(self, symbol):
        if not self.connected:
            if not self.connect():
                print("--- ERROR: No se pudo conectar a MT5 ---")
                return None
        
        try:
            # Ensure symbol is visible
            selected = mt5.symbol_select(symbol, True)
            if not selected:
                log_debug(f"--- ERROR: Símbolo '{symbol}' no encontrado. ---")
                return None
                
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                log_debug(f"--- ERROR: MT5 devolvió tick None para {symbol} ---")
                return None
                
            log_debug(f"--- TICK RECIBIDO DE MT5: {tick.last} ---")
            
            # Gann logic
            if symbol not in self.tick_counts:
                self.tick_counts[symbol] = 0
            self.tick_counts[symbol] += 1
            
            gann_angle = self.tick_counts[symbol] % 360
            spread = tick.ask - tick.bid
            e_draw = min(0.99, max(0.05, (spread * 100) / tick.bid if tick.bid > 0 else 0.5))
            
            return {
                "tick": self.tick_counts[symbol],
                "angle": gann_angle,
                "price": round(tick.last if tick.last > 0 else tick.bid, 2),
                "time": tick.time,
                "e_draw": round(e_draw, 4)
            }
        except Exception as e:
            print(f"--- EXCEPCIÓN EN get_next_tick: {e} ---")
            return None

    def close(self):
        mt5.shutdown()

# Example usage
if __name__ == "__main__":
    market = BridgeMarketData()
    if market.connect():
        for _ in range(5):
            print(market.get_next_tick("Fortune100"))
            time.sleep(1)
        market.close()
