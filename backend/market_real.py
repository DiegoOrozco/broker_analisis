import MetaTrader5 as mt5
import os
import time
from dotenv import load_dotenv

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
        if not mt5.initialize():
            print(f"initialize() failed, error code = {mt5.last_error()}")
            return False
        
        authorized = mt5.login(self.login, password=self.password, server=self.server)
        if authorized:
            print(f"Conectado a Bridge Markets MT5 (Acc: {self.login})")
            self.connected = True
            return True
        else:
            print(f"Falló el login en MT5, error code = {mt5.last_error()}")
            return False

    def get_next_tick(self, symbol):
        if not self.connected:
            if not self.connect():
                return None
        
        # Ensure symbol is visible in MarketWatch
        selected = mt5.symbol_select(symbol, True)
        if not selected:
            print(f"Símbolo {symbol} no encontrado en Bridge Markets.")
            return None
            
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
            
        # Gann logic based on tick count (cycles of 360)
        if symbol not in self.tick_counts:
            self.tick_counts[symbol] = 0
        self.tick_counts[symbol] += 1
        
        gann_angle = self.tick_counts[symbol] % 360
        
        # Real-time E-Draw calculation (Volatility based)
        # Using a simple spread/volatility ratio for demonstration
        # In a real KLRR analysis, this would be more complex
        spread = tick.ask - tick.bid
        e_draw = min(0.99, max(0.05, (spread * 100) / tick.bid if tick.bid > 0 else 0.5))
        
        return {
            "tick": self.tick_counts[symbol],
            "angle": gann_angle,
            "price": round(tick.last if tick.last > 0 else tick.bid, 2),
            "time": tick.time,
            "e_draw": round(e_draw, 4)
        }

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
