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
    def __init__(self):
        self.login = int(os.getenv("MT5_LOGIN", 238555))
        self.password = os.getenv("MT5_PASSWORD", "jF6D7ie#E")
        self.server = os.getenv("MT5_SERVER", "BridgeMarkets-MT5")
        self.connected = False
        self.tick_counts = {}
        # Intentar conectar al inicializar la clase
        self.connect()
        
    def connect(self):
        if self.connected:
            return True
            
        path = r"C:\Program Files\BridgeMarkets MetaTrader 5\terminal64.exe"
        log_debug(f"--- INTENTANDO CONEXIÓN INICIAL A MT5 (Acc: {self.login}) ---")
        
        # Inicialización con login directo
        if not mt5.initialize(path=path, login=self.login, password=self.password, server="BridgeMarkets-MT5"):
            log_debug(f"--- FALLO CRITICO INICIALIZACION: {mt5.last_error()} ---")
            self.connected = False
            return False
        
        log_debug("--- CONEXIÓN EXITOSA AL NÚCLEO MT5 ---")
        self.connected = True
        return True

    def get_next_tick(self, symbol):
        if not self.connected:
            if not self.connect():
                return None
        
        try:
            # Asegurar que el símbolo esté en MarketWatch
            mt5.symbol_select(symbol, True)
            tick = mt5.symbol_info_tick(symbol)
            
            if tick is None:
                # Si no hay tick, probamos reconectar por si acaso
                error = mt5.last_error()
                if error[0] == -10004: # No IPC
                    self.connected = False
                return None
                
            log_debug(f"TICK {symbol}: {tick.last}")
            
            if symbol not in self.tick_counts:
                self.tick_counts[symbol] = 0
            self.tick_counts[symbol] += 1
            
            return {
                "tick": self.tick_counts[symbol],
                "angle": self.tick_counts[symbol] % 360,
                "price": round(tick.last if tick.last > 0 else tick.bid, 2),
                "time": tick.time,
                "e_draw": round(min(0.99, max(0.05, ((tick.ask - tick.bid) * 100) / tick.bid if tick.bid > 0 else 0.5)), 4)
            }
        except Exception as e:
            log_debug(f"Error en tick {symbol}: {e}")
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
