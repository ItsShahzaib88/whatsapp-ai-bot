# 🤖 AI WhatsApp Assistant

> Enterprise-grade AI-powered WhatsApp assistant with per-contact memory, multi-provider AI, personality system, voice support, and a beautiful admin dashboard.

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## ✨ Features

### 🧠 AI & Memory
- **Per-contact AI memory** — name, nickname, birthday, favourites, preferences, relationship
- **Auto memory updates** — AI extracts and updates memory after every conversation
- **Context continuity** — `"continue"` → AI knows what you were talking about
- **Multi-provider AI** — Gemini → Groq → OpenAI → OpenRouter → Together AI (auto-fallback)

### 📱 WhatsApp Integration
- ✅ Webhook verification & security
- ✅ Receive text, voice, image, video, document messages
- ✅ Send text and voice replies
- ✅ Read receipts (blue tick)
- ✅ Delivery status tracking
- ✅ Message queue with retry logic
- ✅ Auto-reply modes (Office, Meeting, Driving, Busy, Vacation, Night)

### 🎭 Personality System
- Custom personality per contact (Family, Friends, Office, Romantic, etc.)
- Configurable: tone, emoji usage, reply length, greeting style, forbidden topics
- Admin-editable from dashboard

### 🎙️ Voice Features
- Voice note → Speech-to-Text → AI → Text-to-Speech → Voice reply
- Supports: English, Urdu, Roman Urdu
- Free: Groq Whisper (STT) + Microsoft Edge TTS

### 🌐 Smart Web Search
- Auto-detects queries needing real-time info (weather, news, sports, prices)
- Weather: Open-Meteo (free, no key)
- News: NewsData.io (free tier)
- General: DuckDuckGo (free, no key)

### 📋 Commands
| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/ai` | Enable AI mode |
| `/human` | Disable AI replies |
| `/memory` | Show what AI knows about you |
| `/reset` | Reset conversation context |
| `/clear` | Clear AI memory |
| `/history` | Show recent messages |
| `/voice` | Toggle voice replies |
| `/status` | System status |
| `/personality` | Show current personality |

### 🖥️ Admin Dashboard
- Beautiful dark/light mode UI (Next.js 15 + Tailwind)
- Real-time statistics and charts
- Contact management with memory viewer/editor
- Conversation viewer with admin broadcast
- Personality template management
- AI provider switcher (live switching)
- System health monitoring
- Audit logs

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                    WhatsApp Cloud API                │
└──────────────────────┬──────────────────────────────┘
                       │ Webhook
                       ▼
┌─────────────────────────────────────────────────────┐
│                  Nginx (SSL Proxy)                   │
└──────────┬───────────────────────┬──────────────────┘
           │                       │
           ▼                       ▼
┌──────────────────┐    ┌──────────────────────────┐
│  FastAPI Backend │    │   Next.js 15 Dashboard   │
│  (Python 3.13)   │    │   (React 19 + Tailwind)  │
└────────┬─────────┘    └──────────────────────────┘
         │
    ┌────┴──────────────────────────┐
    │                               │
    ▼                               ▼
┌────────┐  ┌────────┐  ┌────────────────────────┐
│MongoDB │  │ Redis  │  │   AI Providers          │
│(Motor) │  │(Cache) │  │  Gemini → Groq → OpenAI │
└────────┘  └────────┘  └────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.13+
- Node.js 20+
- MongoDB (Atlas free tier or local)
- Redis (local or cloud)
- Docker + Docker Compose (for production)

### 1. Clone & Configure

```bash
git clone https://github.com/your-username/whatsapp-ai-assistant.git
cd whatsapp-ai-assistant
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys
```

### 2. Start with Docker Compose (Recommended)

```bash
docker compose up -d
```

Services will be available at:
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Frontend Dashboard**: http://localhost:3000

### 3. Start Manually (Development)

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Edit with your values
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

### 4. Access Dashboard

1. Open http://localhost:3000
2. Login with your `ADMIN_EMAIL` and `ADMIN_PASSWORD` from `.env`
3. Default: `admin@example.com` / `changeme_strong_password`

---

## ⚙️ Configuration

### Required API Keys

| Service | Where to Get | Free? |
|---------|-------------|-------|
| Gemini API | [aistudio.google.com](https://aistudio.google.com/app/apikey) | ✅ Free |
| Groq API | [console.groq.com](https://console.groq.com/keys) | ✅ Free |
| WhatsApp | [developers.facebook.com](https://developers.facebook.com) | ✅ Free (1K msg/mo) |
| MongoDB | [mongodb.com/atlas](https://www.mongodb.com/atlas) | ✅ Free |
| OpenAI | [platform.openai.com](https://platform.openai.com) | ❌ Paid |

### WhatsApp Setup
See [docs/WHATSAPP_SETUP.md](docs/WHATSAPP_SETUP.md) for full setup guide.

### VPS Deployment
See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for production deployment guide.

---

## 📁 Project Structure

```
whatsapp-ai-assistant/
├── backend/                    # Python FastAPI backend
│   ├── app/
│   │   ├── api/v1/routers/    # API endpoints
│   │   ├── core/              # Config, security, exceptions
│   │   ├── database/          # MongoDB + Redis connections
│   │   ├── models/            # MongoDB document models
│   │   ├── repositories/      # Data access layer (Repository pattern)
│   │   ├── services/          # Business logic
│   │   │   └── providers/     # AI provider implementations
│   │   ├── prompts/           # AI prompt templates
│   │   ├── voice/             # STT + TTS pipeline
│   │   ├── websearch/         # Web search service
│   │   ├── whatsapp/          # WhatsApp client + webhook parser
│   │   └── middleware/        # Auth, rate limit, logging
│   ├── tests/                 # pytest test suite
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/                   # Next.js 15 admin dashboard
│   ├── src/
│   │   ├── app/               # App Router pages
│   │   ├── lib/               # API client
│   │   ├── store/             # Zustand state management
│   │   └── types/             # TypeScript interfaces
│   ├── package.json
│   └── Dockerfile
├── nginx/                      # Nginx reverse proxy
├── docs/                       # Setup & deployment guides
├── .github/workflows/          # GitHub Actions CI/CD
└── docker-compose.yml
```

---

## 🔒 Security

- JWT Bearer authentication on all API endpoints
- bcrypt password hashing
- CORS configured for allowed origins only
- Rate limiting: 60 req/min per IP (Redis-backed)
- Webhook signature verification
- Environment variable secrets (never committed)
- Non-root Docker containers
- TLS/SSL via Nginx + Let's Encrypt
- Request audit logging

---

## 🧪 Running Tests

```bash
cd backend
pytest tests/ -v --cov=app
```

---

## 📄 License

MIT License — free for personal and commercial use.

---

## 🙏 Credits

- [FastAPI](https://fastapi.tiangolo.com) — Modern Python API framework
- [Google Gemini](https://deepmind.google/technologies/gemini/) — Primary AI provider
- [Groq](https://groq.com) — Fast inference + Whisper STT
- [Edge TTS](https://github.com/rany2/edge-tts) — Free Microsoft Neural TTS
- [Open-Meteo](https://open-meteo.com) — Free weather API
- [DuckDuckGo](https://duckduckgo.com) — Free web search
