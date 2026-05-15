import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def list_available_models():
    api_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    print("--- Modelos disponibles para tu API Key ---")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(m.name)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_available_models()
