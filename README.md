# AI Academic Advisor

A voice-first academic advising web app for hackathon demos. Students open the app and talk to an AI advisor through their microphone. The advisor responds in natural spoken language, grounded in degree audit, course registry, and major requirements via Moss semantic search.

## Tech Stack

- **Frontend:** React + Vite + TailwindCSS
- **Voice pipeline:** LiveKit Agents (Python)
- **Retrieval:** Moss Python SDK (sub-10ms semantic search)
- **LLM + TTS:** MiniMax (`MINIMAX_API_KEY`)
- **STT / TTS:** LiveKit Inference (Deepgram + Cartesia via your LiveKit keys — no separate provider keys)
- **Retrieval:** Moss (`MOSS_PROJECT_ID`, `MOSS_PROJECT_KEY`)

## Project Structure

```
/
├── agent.py              # LiveKit voice agent
├── index_setup.py        # One-time Moss index builder
├── token_server.py       # LiveKit JWT token endpoint for frontend
├── requirements.txt
├── data/
│   ├── degree_audit.json
│   ├── course_registry.json
│   └── major_requirements.json
├── frontend/
│   └── src/components/   # React UI
├── .env.local
└── README.md
```

## Setup

### 1. Fill in `.env.local`

```bash
# Moss
MOSS_PROJECT_ID=
MOSS_PROJECT_KEY=

# LiveKit (transport + Inference STT/TTS)
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=

# MiniMax — LLM + TTS
MINIMAX_API_KEY=
MINIMAX_API_BASE_URL=https://api.minimax.io
MINIMAX_LLM_MODEL=MiniMax-M3
MINIMAX_TTS_MODEL=speech-2.8-hd
MINIMAX_VOICE=English_expressive_narrator
MINIMAX_TTS_MODE=t2a
MINIMAX_LLM_STREAM=false
# global = api.minimax.io (overseas) | cn = api.minimaxi.com (China)
MINIMAX_REGION=global
```

STT runs through LiveKit Inference (Deepgram). LLM and TTS use MiniMax directly.

**MiniMax errors?**
- **401** — key region mismatch. Use `MINIMAX_REGION=global` for [platform.minimax.io](https://platform.minimax.io) keys, or `cn` for [platform.minimaxi.com](https://platform.minimaxi.com).
- **500** — ensure `MINIMAX_LLM_MODEL=MiniMax-M3` and `MINIMAX_API_BASE_URL=https://api.minimax.io`.

### 2. Install Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Populate data files

Fill in `data/degree_audit.json`, `data/course_registry.json`, and `data/major_requirements.json`, then copy to the frontend:

```bash
cp data/*.json frontend/public/data/
```

### 4. Build Moss indexes (run once)

```bash
python index_setup.py
```

### 5. Download agent model files (run once)

The turn detector and Silero VAD need local ONNX weights from Hugging Face:

```bash
python -m livekit.agents download-files
```

### 6. Start the token server (terminal 1)

```bash
python token_server.py
```

### 6. Start the voice agent (terminal 2)

```bash
python agent.py dev
```

For mic-only testing without the frontend:

```bash
python agent.py console
```

### 7. Start the frontend (terminal 3)

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) and start talking.

## 2-Minute Judge Demo Script

1. **Open the app** — show the dark, minimal UI with the student profile on the left.
2. **Point at the profile** — name, major, GPA, degree progress bar, credits remaining.
3. **Tap a chip** — "What can I take next semester?" — mic connects and the advisor answers using live Moss search.
4. **Ask a follow-up** — "What do I need before OS?" — advisor searches prerequisites from the course registry.
5. **Request a plan** — "Build me a graduation plan" — advisor speaks a natural summary while a semester-by-semester table appears inline in the chat.
6. **Close** — emphasize: voice-only product, no hallucination (always searches first), sub-10ms retrieval.

## How It Works

```
Mic → LiveKit → Inference STT → MiniMax LLM + Moss tools → Inference TTS → Speaker
                                      ↓
                              graduation_plan data → React table
```

The agent exposes three Moss search tools plus `show_graduation_plan`, which publishes structured JSON to the frontend via LiveKit data channels while speaking a conversational summary.
