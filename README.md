# Autonomous UPSC Mains Answer Evaluation & Feedback Engine

An autonomous, multi-agent evaluation engine designed to assess UPSC Mains handwritten and digital answer copies, verify facts against authoritative syllabus benchmarks via LLM, and deliver calibrated scores with actionable transformation roadmaps.

The system executes a **Deterministic Native DAG (Directed Acyclic Graph)** using an **Ensemble / "Panel of Judges" Architecture**. Five isolated specialist agents evaluate specific dimensions (Demand, Introduction, Structure, Conclusion, and Knowledge & Facts) concurrently via asynchronous fan-out before a Master Scoring Arbiter synthesizes the final calibrated assessment.

---

## 🏗 System Architecture

```mermaid
graph TD
    A[User / Client] -->|Upload PDF / Text| B[FastAPI Backend]
    B -->|Convert & OCR| C[Vision & PDF Processing]
    C -->|Extracted Question & Answer| D[Deterministic Native DAG Fan-Out]
    
    subgraph Specialist Agents [Panel of Judges]
        D --> E1[Demand Agent]
        D --> E2[Introduction Agent]
        D --> E3[Structure Agent]
        D --> E4[Conclusion Agent]
        D --> E5[Knowledge & Fact Agent]
    end

    E1 --> F[Master Scoring Arbiter]
    E2 --> F
    E3 --> F
    E4 --> F
    E5 --> F

    F --> G[Calibrated Report & Actionable Feedback]
    G --> H[Storage & DB: Supabase / SQLite]
    G --> I[React Web UI]
```

---

## 🚀 Deployment

The platform is deployed across two services:

- **Backend (Render)**: The FastAPI server is deployed as a Docker service on [Render](https://render.com) using the included [Dockerfile](./Dockerfile).
- **Frontend (Vercel)**: The React + Vite client is deployed on [Vercel](https://vercel.com) from the `frontend/` directory, connecting to the Render backend via `VITE_API_BASE_URL`.

---

## 📊 Observability (Langfuse)

The evaluation pipeline includes built-in tracing and monitoring powered by [Langfuse](https://langfuse.com):
- **Multi-Agent Tracing**: Tracks prompts, model calls, latency, token usage, and outputs across all specialist judge agents and the Master Arbiter.
- **Pipeline Spans**: Traces end-to-end stages including PDF/OCR processing, parallel DAG execution, and database persistence.
- **Zero Overhead Setup**: Enabled automatically when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are configured in environment variables.

---

## 💻 Local Development

### Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- `poppler` (for PDF processing):
  - macOS: `brew install poppler`
  - Ubuntu/Debian: `sudo apt-get install -y poppler-utils`

### 1. Backend Setup
```bash
# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your OpenAI and Supabase credentials

# Start FastAPI server
python -m src.api.server
# Server will run at http://127.0.0.1:8000 (Swagger docs at /docs)
```

### 2. Frontend Setup
```bash
cd frontend

# Configure environment variables
cp .env.example .env
# Set VITE_API_BASE_URL=http://127.0.0.1:8000 for local testing

# Install dependencies and start Vite dev server
npm install
npm run dev
# Frontend will run at http://127.0.0.1:5173
```

### 3. Run Both Concurrently
You can also launch both services concurrently using the helper script:
```bash
chmod +x run_dev.sh
./run_dev.sh
```