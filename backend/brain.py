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
        
        try:
            with open("manual_indices.txt", "r", encoding="utf-8") as f:
                manual_text = f.read()
        except FileNotFoundError:
            manual_text = "ERROR: Manual text not found."
            
        # System instructions from the manual
        self.system_instruction = f"""
        Eres un Algoritmo Cuántico de Alta Precisión diseñado EXCLUSIVAMENTE para operar los Índices Sintéticos de Bridge Markets. 
        A continuación, se te provee el "Manual de Anatomía de los Índices", el cual contiene el ADN, las reglas matemáticas, 
        geométricas y de comportamiento para cada índice.
        
        ESTE MANUAL ES TU ÚNICA FUENTE DE VERDAD. No uses suposiciones ni conocimientos externos de trading tradicional. 
        Tu única función es analizar los ticks que te envíe y determinar si se cumple un patrón EXACTO del manual (KLRR, Gann, Wyckoff, E-Draw, etc).
        
        ### MANUAL DE BRIDGE MARKETS (ORO PURO) ###
        {manual_text}
        
        ### INSTRUCCIONES DE EJECUCIÓN ###
        Tu objetivo es identificar el momento exacto para entrar y salir, basado ESTRICTAMENTE en la confluencia de factores del manual.
        - Identifica el cuadrante de Gann (0-90, 90-180, etc) según los ticks.
        - Calcula y considera el E-Draw para el riesgo.
        - Identifica posibles KLRR.
        
        Si no hay confirmación clara según el manual, tu decisión debe ser "WAIT". 
        Si hay confirmación, dame la entrada, un Stop Loss matemático y un Take Profit calculado.

        ### Formato de Salida Obligatorio (JSON sin backticks extra):
        {{
          "decision": "BUY" | "SELL" | "WAIT",
          "type": "Breakout" | "Continuación" | "Scalping" | "Reversión" | "Espera",
          "is_continuation": true | false,
          "reason": "Explicación súper precisa, citando el manual, de por qué se toma esta decisión basado en Gann/KLRR/E-Draw actual",
          "forecast": "Pronóstico proactivo: Basado en las características de ESTE índice específico en el manual que acabas de leer, ¿qué movimiento fuerte se está gestando y hacia dónde nos vamos a montar a corto/mediano plazo?",
          "entry_price": float (precio actual estimado),
          "stop_loss": float (calculado por ti),
          "take_profit": float (calculado por ti),
          "confidence_score": 0.0 a 1.0 (debe ser >0.66 para entrar)
        }}
        """
        self.model = genai.GenerativeModel(
            model_name="gemini-3-flash-preview",
            system_instruction=self.system_instruction
        )

    async def analyze_ticks(self, symbol, ticks_history, prev_signal=None):
        """
        Sends historical market context to Gemini for decision making (Async).
        """
        prev_decision = prev_signal.get('decision') if prev_signal else 'WAIT'
        prev_reason = prev_signal.get('reason') if prev_signal else 'Inicio de análisis'

        prompt = f"""
        ### DATOS DEL MERCADO ACTUAL (VENTANA HISTÓRICA) ###
        - Índice: {symbol}
        - Total de Ticks en memoria: {len(ticks_history)}
        - Estado Sugerido Anterior: {prev_decision} ({prev_reason})
        - Historial Cronológico de Ticks (del más antiguo al más reciente):
        {ticks_history}
        
        ### INSTRUCCIÓN DE ANÁLISIS ESTRUCTURAL Y FILTRO DE RUIDO ###
        Con este historial de ticks, no estás viendo un solo punto, sino la TENDENCIA DE FONDO.
        1. REGLA DE ORO (EVITA EL FLIPEO SCHIZO): En índices sintéticos, cambiar entre BUY y SELL cada 15 segundos arruina la cuenta. Si el estado anterior era BUY/SELL y la estructura de fondo se mantiene (altos más altos, E-Draw controlado), mantén la decisión para dar seguimiento a la operación.
        2. Identifica si el precio está en un rango de acumulación/distribución de Wyckoff o si hay un rompimiento genuino.
        3. Revisa el ángulo de Gann del último tick en relación a los anteriores para ver en qué fase de respiración está.
        4. Si no hay una convergencia clara con una zona KLRR o el mercado está ruidoso, tu decisión OBLIGATORIA es "WAIT" para proteger el capital.

        ### REGLAS DE PROYECCIÓN INSTITUCIONAL (SL y TP AMPLIOS) ###
        ¡PROHIBIDO DAR TAKE PROFITS O STOP LOSS RIDÍCULAMENTE PEQUEÑOS DE 5 O 10 PUNTOS! En los índices sintéticos de Bridge Markets (Fortune, BullX, FomoX), las rupturas de zonas KLRR y descargas de Wyckoff tienen recorridos profundos de alta volatilidad.
        - Para operaciones de BUY o SELL, el Take Profit debe buscar el final de la estructura institucional de descarga (ej. +150 a +450 puntos de distancia desde el precio de entrada, apuntando al objetivo de Fibonacci 1.0 o 1.618 del manual).
        - El Stop Loss debe estar resguardado detrás de la KLRR opuesta o base estructural (ej. -30 a -90 puntos, garantizando un ratio Riesgo:Beneficio institucional de al menos 1:3 a 1:5).
        - En el campo "forecast" (Proyección Proactiva), describe con cifras y fundamentos técnicos del manual hacia dónde se dirigirá este recorrido completo de cientos de puntos.

        Analiza la convergencia estructural y devuelve la decisión en el formato JSON exigido.
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
