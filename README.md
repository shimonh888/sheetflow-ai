# SheetFlow AI

> AI-powered Excel to Dashboard SaaS. Connect Google Drive, select Excel files, and let AI generate live, syncable dashboards.

![SheetFlow AI](https://img.shields.io/badge/SheetFlow-AI-blue?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?style=flat&logo=nextdotjs&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=flat&logo=postgresql&logoColor=white)

## Features

- 🔐 **Google OAuth2** - Secure authentication with Drive read access
- 📊 **Multi-Sheet Processing** - AI analyzes and joins data across multiple sheets
- 🔄 **Schema Drift Detection** - Auto-remaps renamed columns instead of breaking
- 🔒 **Encrypted Token Storage** - OAuth tokens encrypted with Fernet at rest
- 📈 **AI-Generated Charts** - Gemini suggests optimal visualizations
- ⚡ **Live Sync** - One-click refresh from Google Drive

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI (Python 3.11) |
| Database | PostgreSQL 15 |
| AI | LangGraph + Gemini 1.5 Flash |
| Frontend | Next.js 14 + Tailwind CSS |
| Charts | Recharts |
| Icons | Lucide React |

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Google Cloud Console account
- Gemini API key

### 1. Clone and Setup

```bash
cd sheetflow-ai
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

### 2. Configure Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable APIs:
   - Go to **APIs & Services > Library**
   - Enable **Google Drive API**

4. Configure OAuth Consent Screen:
   - Go to **APIs & Services > OAuth consent screen**
   - Choose **External** user type
   - Fill in app name: `SheetFlow AI`
   - Add scopes: 
     - `openid`
     - `email`
     - `profile`
     - `https://www.googleapis.com/auth/drive.readonly`
   - Add test users (your email)

5. Create OAuth Credentials:
   - Go to **APIs & Services > Credentials**
   - Click **Create Credentials > OAuth client ID**
   - Application type: **Web application**
   - Name: `SheetFlow AI`
   - Authorized redirect URIs:
     - `http://localhost:8000/api/auth/callback` (development)
   - Copy **Client ID** and **Client Secret**

### 3. Get Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Create a new API key
3. Copy the key

### 4. Generate Encryption Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 5. Update Environment Variables

Edit `backend/.env`:

```env
SECRET_KEY=generate-a-random-string-here
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
ENCRYPTION_KEY=your-fernet-key-from-step-4
GEMINI_API_KEY=your-gemini-api-key
```

### 6. Start with Docker

```bash
docker-compose up --build
```

### 7. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs

---

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/auth/login` | Get Google OAuth URL |
| GET | `/api/auth/callback` | OAuth callback handler |
| GET | `/api/auth/me` | Get current user |

### Dashboards

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboards` | List all dashboards |
| POST | `/api/dashboards` | Create dashboard |
| GET | `/api/dashboards/{id}` | Get dashboard |
| POST | `/api/dashboards/{id}/refresh` | **Sync from Drive** |
| GET | `/api/dashboards/{id}/data` | Get chart data |

---

## Project Structure

```
sheetflow-ai/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry
│   │   ├── config.py         # Settings
│   │   ├── database.py       # PostgreSQL
│   │   ├── models.py         # SQLAlchemy models
│   │   ├── routers/
│   │   │   ├── auth.py       # OAuth2 flow
│   │   │   └── dashboards.py # Dashboard CRUD + Refresh
│   │   ├── services/
│   │   │   ├── encryption.py # Token encryption
│   │   │   ├── google_drive.py
│   │   │   └── ai_agent.py   # LangGraph workflow
│   │   └── agents/
│   │       ├── data_processor.py  # Pandas cleaning
│   │       └── schema_mapper.py   # Drift detection
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── page.tsx      # Landing page
│       │   └── dashboard/
│       │       └── [id]/page.tsx
│       └── components/
│           ├── SyncButton.tsx
│           └── ChartContainer.tsx
├── docker/
│   └── init.sql
├── docker-compose.yml
└── README.md
```

---

## Development

### Run Backend Locally

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Run Frontend Locally

```bash
cd frontend
npm install
npm run dev
```

---

## License

MIT
