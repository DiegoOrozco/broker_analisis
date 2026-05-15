import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def test_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ ERROR: No se encontró GEMINI_API_KEY en el archivo .env")
        return False
    
    print(f"--- Probando conexión con Gemini API ---")
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content("Hola, responde solo con la palabra 'OK' si recibes este mensaje.")
        
        if "OK" in response.text.upper():
            print("✅ CONEXIÓN EXITOSA: La API de Gemini está respondiendo correctamente.")
            return True
        else:
            print(f"⚠️ RESPUESTA INESPERADA: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ FALLO DE CONEXIÓN: {str(e)}")
        if "API_KEY_INVALID" in str(e):
            print("👉 Sugerencia: Tu API Key parece ser inválida. Genera una nueva en Google AI Studio.")
        return False

if __name__ == "__main__":
    test_gemini()
