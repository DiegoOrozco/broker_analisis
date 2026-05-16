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
          "decision": "BUY" | "SELL" | "WAIT" | "PENDING_BUY" | "PENDING_SELL",
          "type": "Breakout" | "Continuación" | "Scalping" | "Reversión" | "Espera" | "Orden Programada",
          "is_continuation": true | false,
          "reason": "Explicación súper precisa, citando el manual, de por qué se toma esta decisión. Si es PENDING_BUY/SELL, explica por qué ese precio futuro es el punto clave.",
          "forecast": "Pronóstico proactivo: Basado en las características de ESTE índice específico, ¿qué movimiento fuerte se gesta a mediano plazo?",
          "target_entry_price": float (SOLO si la decisión es PENDING_BUY o PENDING_SELL, indica el precio exacto futuro donde debe activarse. Si es BUY, SELL o WAIT pon 0),
          "entry_price": float (precio actual estimado),
          "stop_loss": float (calculado por ti),
          "take_profit": float (calculado por ti),
          "confidence_score": 0.0 a 1.0 (debe ser >0.66 para entrar o programar)
        }}
        """
        self.model = genai.GenerativeModel(
            model_name="gemini-3-flash-preview",
            system_instruction=self.system_instruction
        )

    async def analyze_ticks(self, symbol, ticks_history, prev_signal=None, locked_trade=None):
        """
        Sends historical market context to Gemini for decision making (Async).
        """
        prev_decision = prev_signal.get('decision') if prev_signal else 'WAIT'
        prev_reason = prev_signal.get('reason') if prev_signal else 'Inicio de análisis'

        locked_context = ""
        if locked_trade:
            locked_context = f"""
        ### POSICIÓN REAL ACTIVA EN CURSO ({locked_trade.get('decision')} en {symbol}) ###
        - Precio de entrada: {locked_trade.get('entry_price')}
        - SL actual: {locked_trade.get('stop_loss')} / TP actual: {locked_trade.get('take_profit')}
        
        MISIÓN CRÍTICA DE GESTIÓN Y PROTECCIÓN DE GANANCIAS (KLRR & WYCKOFF):
        - Tu tarea EXCLUSIVA es monitorear esta operación activa.
        - REGLA DE PROTECCIÓN DE BENEFICIOS (ES MEJOR $50 EN BOLSILLO QUE $0 POR ESPERAR): Si la operación se encuentra con ganancias notables (ej. +20, +40 o +50 puntos o dólares a favor) y observas en el flujo de ticks que la vela está perdiendo impulso, formando una divergencia KLRR, o entrando en zona de agotamiento/distribución Wyckoff, tu decisión OBLIGATORIA debe ser "EXIT" o "SALIR". Esto le ordenará al servidor cerrar la orden a mercado de inmediato y embolsar los dólares de ganancia real en la cuenta.
        - Si la tendencia sigue con fuerza arrolladora hacia el Take Profit sin signos de agotamiento, devuelve la misma decisión ("BUY" o "SELL") para dejarla correr.
        """

        prompt = f"""
        ### DATOS DEL MERCADO ACTUAL (VENTANA HISTÓRICA) ###
        - Índice: {symbol}
        - Total de Ticks en memoria: {len(ticks_history)}
        - Estado Sugerido Anterior: {prev_decision} ({prev_reason})
        {locked_context}
        - Historial Cronológico de Ticks (del más antiguo al más reciente):
        {ticks_history}
        
        ### INSTRUCCIÓN DE ANÁLISIS ESTRUCTURAL Y FILTRO DE RUIDO ###
        Con este historial de ticks, no estás viendo un solo punto, sino la TENDENCIA DE FONDO.
        1. REGLA DE ORO (EVITA EL FLIPEO SCHIZO): En índices sintéticos, cambiar entre BUY y SELL cada 15 segundos arruina la cuenta. Si el estado anterior era BUY/SELL y la estructura de fondo se mantiene (altos más altos, E-Draw controlado), mantén la decisión para dar seguimiento a la operación.
        2. Identifica si el precio está en un rango de acumulación/distribución de Wyckoff o si hay un rompimiento genuino.
        3. Revisa el ángulo de Gann del último tick en relación a los anteriores para ver en qué fase de respiración está.
        4. OBLIGACIÓN DE ESPERA (WAIT) Y RIGOR EXTREMO ANTI-PÉRDIDAS: El usuario reporta una pérdida de -67 dólares por una entrada prematura en BUY. Si la estructura no muestra una acumulación impecable en Wyckoff, o si el conteo de Gann no está en el punto exacto de quiebre (180° para spikes), O SI LA ESTRUCTURA DE MERCADO (Price Action) va en contra (ej. buscando BUY pero los máximos y mínimos cada vez son más bajos), tu decisión OBLIGATORIA e innegociable es "WAIT". 
        5. ESTRUCTURA DE MERCADO (NUEVO CRITERIO): Antes de lanzar un BUY, verifica que haya un quiebre de estructura alcista (Break of Structure - BOS) y un retroceso a un Order Block claro. Para SELL, lo inverso. No dispares en "tierra de nadie". Solo lanza BUY/SELL en setups inmaculados donde Wyckoff, Gann y Estructura de Mercado se alineen.

        ### REGLAS DE FRANCOTIRADOR (SNIPER ENTRY: SL TIGHT & TP AMPLIO) ###
        ¡El usuario exige entradas de alta precisión milimétrica en el punto exacto de quiebre KLRR!
        - STOP LOSS ESTRICTO (MÁXIMO 10 PUNTOS/PIPS): El Stop Loss DEBE estar posicionado a un máximo absoluto de 10 puntos de distancia del precio de entrada estimado (ej. si entras en BUY a 12000, el Stop Loss no puede ser menor a 11990; si es SELL a 12000, no mayor a 12010). Buscamos el punto exacto de inflexión donde el riesgo es mínimo.
        - TAKE PROFIT AMPLIO INSTITUCIONAL: El Take Profit debe proyectar el recorrido completo del estallido o descarga de Wyckoff (+150 a +450 puntos de distancia desde el precio de entrada, apuntando a Fibonacci 1.0 o 1.618 del manual).
        - Con esto garantizamos un ratio Riesgo:Beneficio espectacular de francotirador (1:15 a 1:45).
        - En el campo "forecast" (Proyección Proactiva), describe con cifras y fundamentos técnicos del manual hacia dónde se dirigirá este estallido masivo de cientos de puntos y por qué el nivel actual permite un stop tan ceñido.

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
