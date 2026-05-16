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
        log_debug(f"--- INTENTANDO CONEXION INICIAL A MT5 (Acc: {self.login}) ---")
        
        if not mt5.initialize(path=path):
            log_debug(f"--- FALLO INICIALIZACION MT5: {mt5.last_error()} ---")
            self.connected = False
            return False
            
        authorized = mt5.login(int(self.login), password=self.password, server="BridgeMarkets-MT5")
        if not authorized:
            log_debug(f"--- FALLO LOGIN MT5: {mt5.last_error()} ---")
            self.connected = False
            return False
            
        log_debug("--- CONEXION EXITOSA AL NUCLEO MT5 ---")
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
                log_debug(f"Tick is None for symbol '{symbol}'. MT5 Error: {error}")
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

    def preload_history(self, symbol, count=300):
        if not self.connected:
            if not self.connect():
                return []
        try:
            mt5.symbol_select(symbol, True)
            historical = mt5.copy_ticks_from_pos(symbol, 0, count, mt5.COPY_TICKS_ALL)
            if historical is None or len(historical) == 0:
                return []
                
            preloaded = []
            if symbol not in self.tick_counts:
                self.tick_counts[symbol] = 0
                
            for h in historical:
                self.tick_counts[symbol] += 1
                bid = float(h['bid'])
                ask = float(h['ask'])
                last = float(h['last'])
                price = round(last if last > 0 else bid, 2)
                if price <= 0:
                    continue
                e_draw = round(min(0.99, max(0.05, ((ask - bid) * 100) / bid if bid > 0 else 0.5)), 4)
                preloaded.append({
                    "tick": self.tick_counts[symbol],
                    "angle": self.tick_counts[symbol] % 360,
                    "price": price,
                    "time": int(h['time']),
                    "e_draw": e_draw
                })
            log_debug(f"Preloaded {len(preloaded)} ticks for {symbol}")
            return preloaded
        except Exception as e:
            log_debug(f"Error preloading history for {symbol}: {e}")
            return []

    def execute_trade(self, symbol, decision, lot_size, sl, tp):
        if not self.connected:
            return {"success": False, "error": "No conectado a MT5"}
            
        mt5.symbol_select(symbol, True)
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return {"success": False, "error": f"Símbolo no encontrado: {symbol}"}
            
        point = symbol_info.point
        tick = mt5.symbol_info_tick(symbol)
        price = tick.ask if decision == "BUY" else tick.bid
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot_size),
            "type": mt5.ORDER_TYPE_BUY if decision == "BUY" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": float(sl),
            "tp": float(tp),
            "deviation": 20,
            "magic": 234000,
            "comment": "Antigravity AI Sniper",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Orden rechazada: {result.comment} (Code: {result.retcode})"
            log_debug(error_msg)
            return {"success": False, "error": error_msg}
            
        log_debug(f"¡ORDEN EJECUTADA EN MT5! {decision} en {symbol} a {price}. Ticket: {result.order}")
        return {
            "success": True,
            "ticket": result.order,
            "price": result.price,
            "volume": result.volume
        }

    def modify_trade(self, symbol, ticket, sl, tp):
        if not self.connected:
            return {"success": False, "error": "No conectado a MT5"}
            
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "position": int(ticket),
            "sl": float(sl),
            "tp": float(tp)
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Modificación SL/TP rechazada: {result.comment} (Code: {result.retcode})"
            log_debug(error_msg)
            return {"success": False, "error": error_msg}
            
        log_debug(f"¡POSICIÓN {ticket} MODIFICADA EN MT5! SL: {sl}, TP: {tp}")
        return {"success": True, "ticket": ticket, "sl": sl, "tp": tp}

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
