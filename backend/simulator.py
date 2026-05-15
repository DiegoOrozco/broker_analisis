import numpy as np
import pandas as pd
import time
import random

class SyntheticIndexSimulator:
    """
    Simulates Bridge Markets Synthetic Indices following the 'Anatomía' manual.
    - 66% Determinism (Cycles/Steps)
    - 34% Random Variance
    - Gann Cycles (360 ticks)
    """
    def __init__(self, symbol="FortuneX"):
        self.symbol = symbol
        # Precios base más realistas según el broker
        base_prices = {
            "FortuneX": 50000.0,
            "BullX1000": 1500.0,
            "BearX1000": 1500.0,
            "Vortex": 500.0,
            "FomoX": 2500.0
        }
        self.price = base_prices.get(symbol, 1000.0)
        self.tick_count = 0
        self.history = []
        
    def get_next_tick(self):
        self.tick_count += 1
        gann_angle = self.tick_count % 360
        
        # 1. Deterministic component (Gann phases)
        trend = 0
        if 90 <= gann_angle <= 180:
            trend = 0.8 if "Bull" in self.symbol or "Fortune" in self.symbol else 0.2
        elif 270 <= gann_angle <= 360:
            trend = -0.8 if "Bear" in self.symbol else -0.3
            
        # 2. Random component (34%)
        volatility = 0.5 if self.symbol == "Vortex" else 0.2
        noise = np.random.normal(0, volatility)
        
        # 3. Personality based jumps
        jump = 0
        if self.symbol == "FortuneX" and self.tick_count % 80 == 0:
            jump = 10.0
        elif self.symbol == "Vortex" and self.tick_count % 10 == 0:
            jump = random.uniform(-2, 2) # High frequency noise
            
        self.price += trend + noise + jump
        
        tick_data = {
            "tick": self.tick_count,
            "angle": gann_angle,
            "price": round(self.price, 2),
            "time": time.time(),
            "e_draw": round(random.uniform(0.1, 0.75), 2)
        }
        
        self.history.append(tick_data)
        return tick_data

if __name__ == "__main__":
    sim = SyntheticIndexSimulator()
    for _ in range(10):
        print(sim.get_next_tick())
        time.sleep(0.1)
