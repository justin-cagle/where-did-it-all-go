# Local Models

Using a local AI model means your financial data never leaves your server. This is the recommended setup for privacy-first users.

## Option 1: Ollama (recommended)

[Ollama](https://ollama.com) is the simplest way to run local language models. It handles model management, GPU/CPU inference, and a compatible API.

### Enable Ollama in docker-compose

WDIAG's compose file includes an optional Ollama service. Enable it via the compose profile:

```bash
# In .env:
COMPOSE_PROFILES=bundled-proxy,ollama
```

Then restart:

```bash
docker compose up -d
```

Ollama starts on port 11434 inside the compose network (accessible to the app as `http://ollama:11434`).

### Pull a model

```bash
# Pull a recommended model (inside the Ollama container)
docker compose exec ollama ollama pull llama3

# Or pull mistral:
docker compose exec ollama ollama pull mistral
```

On first pull, the model downloads (2–8 GB depending on the model). Subsequent starts use the cached model.

### Connect WDIAG to Ollama

In **Settings → AI → Add Provider**:

- Type: **Local Ollama**
- URL: `http://ollama:11434` (if using the bundled compose service)
- Model: `llama3` (or whatever you pulled)
- Privacy level: `full` (recommended for local — data stays on your server)

### Recommended models for finance Q&A

| Model | Size | Notes |
|-------|------|-------|
| `llama3` | 4.7 GB | Good balance of capability and speed |
| `mistral` | 4.1 GB | Fast, good at following instructions |
| `llama3:8b` | 4.7 GB | Same as llama3, explicit size |
| `phi3:mini` | 2.2 GB | Small and fast; less capable |

Models run on CPU if no GPU is available. CPU inference is slower but works — expect several seconds per response instead of under a second.

### Performance expectations

- **With a capable GPU:** responses in 1–5 seconds
- **CPU only (modern multi-core):** responses in 15–60 seconds depending on model size and query complexity
- **CPU only (low-end server):** responses may take several minutes

If your server is CPU-only and underpowered, consider a smaller model (`phi3:mini`) or use a cloud provider for AI features.

## Option 2: llama.cpp server

[llama.cpp](https://github.com/ggerganov/llama.cpp) is a high-performance C++ inference engine. Use it if you want more control over model loading, quantization, or hardware configuration.

Run the llama.cpp server:

```bash
./llama-server \
  --model /path/to/your-model.gguf \
  --host 0.0.0.0 \
  --port 8080
```

Then in WDIAG, add a provider:

- Type: **Local llama.cpp**
- URL: `http://your-server:8080`
- Model: (the model name you loaded)
- Privacy level: `full`

The llama.cpp server exposes an OpenAI-compatible API. WDIAG uses this interface.

## Using an external Ollama instance

If you run Ollama on a separate machine (e.g., a desktop with a GPU, and WDIAG on a VPS):

```
Provider URL: http://192.168.1.x:11434
```

The URL is the IP or hostname of the machine running Ollama, with port 11434. Make sure the Ollama instance is accessible from your WDIAG server (check firewall rules).
