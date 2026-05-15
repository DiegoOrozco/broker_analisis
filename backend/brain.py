import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

class TradingBrain:
    """
    The cognitive engine based on the 'Anatomía' manual.
    """
    def __init__(self, api_key=None):
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("Warning: GEMINI_API_KEY not found.")
        genai.configure(api_key=api_key)
        
        # System instructions from the manual
        self.system_instruction = """
        Eres un Algoritmo de Trading Cuántico especializado en los Índices Sintéticos de Bridge Markets. 
        Tu objetivo es identificar Key Levels de Reacción Rápida (KLRR) con una precisión estadística superior al 66%.

        ### Reglas de Análisis Físico-Matemático:
        1. **Ciclos de Gann:** El mercado respira cada 360 ticks. Identifica el cuadrante:
           - 0-90°: Acumulación de energía.
           - 90-180°: Liberación (Spike esperado).
           - 180-270°: Compresión/Retest.
           - 270-360°: Redistribución.
        2. **Convergencia KLRR:** Solo autorizarás una entrada si hay convergencia entre un Ángulo de Gann, una Fase de Wyckoff y un Nivel de Fibonacci dinámico.
        3. **Determinismo:** El 66% del movimiento es predecible, el 34% es ruido inductivo.

        ### Gestión de Riesgo:
        - No operes si el E-Draw (Energy Drawdown) es > 0.6.
        - Duración mínima: 1 minuto.
        - Máximo 4% de exposición.

        ### Formato de Salida Obligatorio (JSON):
        {
          "decision": "BUY" | "SELL" | "WAIT",
          "type": "Continuación de Tendencia" | "Respiro/Scalping" | "Reversión",
          "is_continuation": boolean,
          "reason": "Explicación técnica basada en el manual",
          "entry_price": float,
          "stop_loss": float,
          "take_profit": float,
          "confidence_score": 0.0-1.0
        }
        """
        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=self.system_instruction
        )

    async def analyze_ticks(self, symbol, ticks_data):
        """
        Sends current market context to Gemini for decision making (Async).
        """
        prompt = f"""
        ### DATOS DEL MERCADO ACTUAL ###
        - Índice: {symbol}
        - Ticks: {ticks_data}
        
        Analiza la convergencia de estos datos con el manual técnico y devuelve la decisión en JSON.
        """
        try:
            # Run in a thread if the library is not native async, 
            # but genai 0.8+ has async support. Let's use the async method.
            response = await self.model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            return {
                "decision": "WAIT",
                "reason": f"Error de IA: {str(e)}. Verifique su GEMINI_API_KEY en .env",
                "type": "Error de Sistema"
            }

if __name__ == "__main__":
    brain = TradingBrain()
    # Test call
    # print(brain.analyze_ticks("FortuneX", [{"price": 1050, "angle": 120, "e_draw": 0.2}]))
