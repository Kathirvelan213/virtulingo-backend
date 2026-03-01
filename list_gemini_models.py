"""List available Gemini models to find the correct model name."""
import os
from google import genai

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("Error: GOOGLE_API_KEY not set")
    exit(1)

client = genai.Client(api_key=api_key)

print("Available Gemini models:")
print("-" * 80)

try:
    models = client.models.list()
    for model in models:
        print(f"Model: {model.name}")
        print(f"  Display Name: {model.display_name if hasattr(model, 'display_name') else 'N/A'}")
        print(f"  Supported Methods: {model.supported_generation_methods if hasattr(model, 'supported_generation_methods') else 'N/A'}")
        print()
except Exception as e:
    print(f"Error listing models: {e}")
