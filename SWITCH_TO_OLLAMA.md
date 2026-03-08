# Switch to Local Ollama (Faster & More Reliable)

Gemini API is experiencing issues (503 errors, timeouts). Local Ollama is faster for development.

## Setup (5 minutes):

### 1. Install Ollama
Download: https://ollama.com/download/windows

### 2. Download a fast model
```powershell
ollama pull llama3.2:3b
```

### 3. Update `.env`
```env
# Comment out Gemini (keep as backup)
# GOOGLE_API_KEY=AIzaSyBMuush6FsoLjaQqrMZE1ksNl9q9DZPFUc
# GEMINI_MODEL=gemini-1.5-flash

# Use Ollama instead
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
```

### 4. Update `_bootstrap/bootstrap.py`
```python
# Change line 19:
from infrastructures.LLM import OllamaLLM  # Instead of GeminiLLM

# Change line 42:
self.llm_service = OllamaLLM()  # Instead of GeminiLLM()
```

### 5. Restart backend
```powershell
python main.py
```

## Benefits:
- ✅ **No network timeouts** (runs locally)
- ✅ **No API rate limits** (unlimited)
- ✅ **No 503 errors** (always available)
- ✅ **Faster responses** (~500ms vs 1-3s + network latency)
- ✅ **Free & offline** (no API costs)

## Model Recommendations:
- `llama3.2:3b` - Fast, good for conversations (recommended)
- `llama3.2:1b` - Fastest, simpler responses
- `phi3:mini` - Balanced speed/quality

Test in Unity - should work immediately!
