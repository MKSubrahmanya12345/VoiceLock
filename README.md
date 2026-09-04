# 🛡️ CallShield

**Real-time voice authentication and AI deepfake detection for secure phone calls**

CallShield is a comprehensive security platform that combines passive voice biometrics, AI-generated speech detection, and social engineering risk analysis to protect sensitive phone conversations. Built for modern web applications with real-time processing capabilities.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14+-black.svg)](https://nextjs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 Features

### 🎤 **Voice Authentication**
- Passive speaker verification using SpeechBrain ECAPA-TDNN embeddings
- Real-time voice matching against enrolled user profiles
- Cosine similarity scoring with configurable thresholds

### 🤖 **AI Deepfake Detection**
- Integration with Aurigin.AI for synthetic voice detection
- Continuous analysis of audio streams for AI-generated speech
- Probabilistic scoring with adjustable sensitivity

### 🚨 **Social Engineering Detection**
- Transcript analysis using Google Gemini AI
- Detection of manipulation tactics, urgency patterns, and suspicious phrases
- Risk scoring and real-time alerting

### 📊 **Real-time Risk Dashboard**
- Live risk scoring with multi-factor analysis
- Visual indicators for voice match, deepfake likelihood, and social engineering
- Session management with comprehensive audit trails

### 🎭 **Configurable Agent Scripts**
- Pluggable conversation scenarios (banking, tech support, etc.)
- Dynamic TTS voice generation using Fish Audio
- Script-based timing and conversation flow

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Next.js)                      │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────────────┐ │
│  │ Enrollment │  │  Live Call  │  │  Risk Dashboard      │ │
│  │   Portal   │  │  Interface  │  │  (Real-time Metrics) │ │
│  └────────────┘  └─────────────┘  └──────────────────────┘ │
└─────────────────────┬───────────────────────────────────────┘
                      │ WebSocket + REST API
┌─────────────────────┴───────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │   Session     │  │    Audio     │  │   Risk Engine    │ │
│  │   Manager     │  │  Processor   │  │  (Multi-factor)  │ │
│  └───────────────┘  └──────────────┘  └──────────────────┘ │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │     Voice     │  │  Deepfake    │  │  Social Eng.     │ │
│  │  Verification │  │  Detector    │  │  Detector        │ │
│  │ (SpeechBrain) │  │ (Aurigin.AI) │  │ (Gemini AI)      │ │
│  └───────────────┘  └──────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
CallShield/
├── backend/                      # FastAPI backend service
│   ├── app/
│   │   ├── api/                  # REST & WebSocket endpoints
│   │   │   ├── agent.py         # Agent TTS and scripts
│   │   │   ├── enrollment.py    # Voice enrollment
│   │   │   ├── sessions.py      # Session management
│   │   │   └── websocket.py     # Audio streaming
│   │   ├── services/             # Core business logic
│   │   │   ├── agent_script.py  # Conversation scripts
│   │   │   ├── audio_processor.py
│   │   │   ├── deepfake_detector.py
│   │   │   ├── risk_engine.py
│   │   │   ├── session_manager.py
│   │   │   ├── social_engineering.py
│   │   │   ├── tts_service.py
│   │   │   └── voice_embedding.py
│   │   ├── models/               # Pydantic schemas
│   │   ├── config.py            # Configuration management
│   │   └── main.py              # FastAPI app entry
│   ├── pyproject.toml           # Python dependencies
│   └── .env                     # Environment variables
├── frontend/                     # Next.js frontend application
│   ├── app/                     # Next.js App Router
│   │   ├── (app)/               # Protected routes
│   │   │   ├── call/           # Live call interface
│   │   │   ├── dashboard/      # Risk monitoring
│   │   │   └── enrollment/     # Voice enrollment
│   │   └── page.tsx            # Landing page
│   ├── components/              # React components
│   │   ├── AgentDisplay.tsx
│   │   ├── AudioRecorder.tsx
│   │   ├── ControlPanel.tsx
│   │   ├── RiskDashboard.tsx
│   │   └── ui/                 # shadcn/ui components
│   ├── hooks/                   # Custom React hooks
│   │   ├── useAgentAudio.ts
│   │   ├── useAudioCapture.ts
│   │   ├── useCallSession.ts
│   │   └── useRiskPolling.ts
│   ├── services/                # API client
│   └── lib/                     # Utilities
├── data/                         # Data storage
│   ├── embeddings/              # Voice embeddings (.npy)
│   └── enrollments/             # Enrollment audio
├── pretrained_models/           # ML model files
└── PRD.md                       # Product Requirements Document
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **npm or yarn**
- **API Keys** (see Configuration section)

### 1. Clone the Repository

```bash
git clone https://github.com/shreyk2/CallShield.git
cd CallShield
```

### 2. Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Create .env file (see Configuration section)
cp .env.example .env
# Edit .env with your API keys

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 3. Frontend Setup

```bash
# Navigate to frontend (from project root)
cd frontend

# Install dependencies
npm install

# Create .env.local file
cp .env.example .env.local
# Add your environment variables

# Run development server
npm run dev
```

Frontend will be available at `http://localhost:3000`

---

## ⚙️ Configuration

### Backend Environment Variables (`.env`)

```bash
# Application
DEBUG=True

# Server
HOST=0.0.0.0
PORT=8000

# CORS
CORS_ORIGINS=["http://localhost:3000"]

# Audio Processing
SAMPLE_RATE=16000
AUDIO_CHUNK_SIZE=16000

# Voice Authentication
EMBEDDING_MODEL=speechbrain/spkrec-ecapa-voxceleb
MATCH_THRESHOLD=0.8

# Deepfake Detection (Aurigin.AI)
AURIGIN_API_URL=https://aurigin.ai/api-ext
AURIGIN_API_KEY=your_aurigin_key_here
FAKE_THRESHOLD=0.2

# Text-to-Speech (Fish Audio)
FISH_AUDIO_API_KEY=your_fish_audio_key_here
FISH_AUDIO_MODEL=fish-speech-1.5
FISH_AUDIO_REFERENCE_ID=your_voice_reference_id

# AI Analysis (Google Gemini)
GEMINI_API_KEY=your_gemini_key_here

# Authentication (Supabase)
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_JWT_SECRET=your_jwt_secret

# Data Paths
DATA_DIR=../data
ENROLLMENTS_DIR=../data/enrollments
EMBEDDINGS_DIR=../data/embeddings
```

### Frontend Environment Variables (`.env.local`)

```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000

# Supabase (Authentication)
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
```

---

## 📖 API Documentation

### Key Endpoints

#### **Session Management**
- `POST /sessions` - Create new call session
- `GET /sessions/{session_id}/risk` - Get real-time risk assessment
- `GET /sessions/{session_id}/status` - Check session status

#### **Voice Enrollment**
- `POST /enrollment/enroll` - Upload enrollment audio
- `GET /enrollment/list` - List enrolled users
- `DELETE /enrollment/{user_id}` - Remove enrollment

#### **Agent Scripts**
- `GET /agent/script` - Get current agent script with timing
- `GET /agent/audio/{segment_index}` - Generate TTS audio for segment

#### **WebSocket**
- `WS /ws/audio?session_id={id}` - Stream caller audio (PCM 16-bit, 16kHz mono)

For complete API documentation, visit `http://localhost:8000/docs` when running the backend.

---

## 🎓 Usage Guide

### 1. Enroll a User

```bash
# Using the enrollment script
cd backend
python enroll_user.py --user-id john_doe --duration 10

# Or via API
curl -X POST "http://localhost:8000/enrollment/enroll" \
  -H "Content-Type: multipart/form-data" \
  -F "audio=@enrollment_audio.wav" \
  -F "user_id=john_doe"
```

### 2. Start a Secure Call

1. Navigate to `http://localhost:3000/call`
2. Click "Start Call"
3. Grant microphone permissions
4. The agent will greet you and guide the conversation
5. Monitor the risk dashboard in real-time

### 3. Review Risk Analysis

The dashboard displays:
- **Voice Match Score** (0-100): How closely the voice matches enrollment
- **Deepfake Score** (0-100): Likelihood of AI-generated speech
- **Social Engineering Risk**: Detection of manipulation tactics
- **Overall Status**: SAFE, UNCERTAIN, or HIGH_RISK

---

## 🧪 Testing

### Backend Tests

```bash
cd backend

# Run all tests
pytest

# Run specific test file
pytest test_phase2.py

# Run with coverage
pytest --cov=app --cov-report=html
```

### Frontend Tests

```bash
cd frontend

# Run tests
npm test

# Run with coverage
npm test -- --coverage
```

---

## 🔒 Security Considerations

- **Voice embeddings** are stored locally and never transmitted
- **Audio streams** are processed in real-time and not persisted
- **API keys** should be kept secure and never committed to version control
- **Authentication** uses Supabase JWT tokens
- **CORS** is configured to restrict access to trusted origins

---

## 🛠️ Technology Stack

### Backend
- **FastAPI** - High-performance async web framework
- **WebSockets** - Real-time bidirectional communication
- **SpeechBrain** - Speaker verification (ECAPA-TDNN)
- **PyTorch** - Deep learning operations
- **Aurigin.AI** - Deepfake detection API
- **Fish Audio** - Neural text-to-speech
- **Google Gemini** - Social engineering analysis

### Frontend
- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe development
- **Tailwind CSS** - Utility-first styling
- **shadcn/ui** - Accessible UI components
- **Web Audio API** - Audio capture and processing
- **Supabase** - Authentication and user management

### Infrastructure
- **Supabase** - PostgreSQL database and auth
- **Vercel** - Frontend deployment (optional)
- **Docker** - Containerization (optional)

---

## 📈 Performance

- **Latency**: <200ms for voice verification
- **Deepfake Detection**: ~2-3 seconds per analysis
- **WebSocket Throughput**: Supports 100+ concurrent sessions
- **Audio Processing**: Real-time at 16kHz sample rate

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **SpeechBrain** team for the ECAPA-TDNN speaker verification model
- **Aurigin.AI** for deepfake detection capabilities
- **Fish Audio** for high-quality TTS
- **Google** for Gemini AI API
- **Supabase** for authentication infrastructure

---

## 📞 Support

- **Documentation**: [API_DOCS.md](backend/API_DOCS.md)
- **Issues**: [GitHub Issues](https://github.com/shreyk2/CallShield/issues)
- **Email**: support@callshield.example.com

---

## 🌟 Star History

If you find CallShield useful, please consider giving it a star ⭐️

---

**Built with ❤️ by the CallShield Team**
#   V o i c e L o c k  
 