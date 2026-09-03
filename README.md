# BIS AI Assistant

A document-grounded chatbot for Indian Standards, BIS certification, Quality Control Orders, and Gazette notifications.

The application uses retrieval-augmented generation (RAG): it searches the supplied BIS PDF documents and gives the relevant passages to an LLM. The PDFs are not used to modify model weights, and no database is required.

## Features

- BIS-focused question answering
- Local PDF indexing at backend startup
- Page-aware source citations
- Structured answers with direct answer, evidence, regulation, next step, and sources
- Confidence score and confidence explanation
- English, Hindi, and Bengali response selection
- Exact-term and synonym-aware retrieval for questions such as "electric bulb" and "LED lamp"
- OpenAI-compatible LLM provider with a local retrieval fallback
- React and Vite frontend
- FastAPI backend

## Knowledge Sources

The backend automatically indexes PDF files stored in `frontend/`:

- `bis_rag_knowledge_dataset_modified.pdf`
- `Gazette-Notification.pdf`
- `BIS-CA-6th-Amendment-Regulations-2021-Gazette.pdf`
- `BIS-CA-4th-Amendment-Regulations-2021-Gazette.pdf`
- `BIS_ROD_Order_12092019.pdf`
- `BIS-Rules-2018_amendments_Sep_15102020.pdf`

To add another document, copy a readable PDF into `frontend/` and add its filename to `PDF_PATHS` in `backend/app/services/retrieval/local_knowledge.py`.

## Requirements

- Windows, macOS, or Linux
- Python 3.13 recommended
- Node.js and npm
- An OpenAI API key for natural summarized answers

PostgreSQL, Docker, and a database are not required.

## Setup

### 1. Create the Python environment

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### 2. Install backend dependencies

```powershell
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
```

### 3. Configure the LLM

Copy the example file:

```powershell
Copy-Item backend\.env.example backend\.env
```

Edit `backend/.env`:

```env
LLM_PROVIDER=openai
LLM_API_KEY=your_api_key_here
LLM_MODEL=gpt-4o-mini
LLM_MAX_TOKENS=1024
LLM_TEMPERATURE=0.2
```

Keep the real key private. The repository `.gitignore` excludes `.env` files.

An API key is optional. Without available LLM credits, the chatbot uses a structured local retrieval fallback. The fallback is grounded in the indexed PDFs but is less fluent than an LLM response.

## Run the Application

Use two terminals from the repository root.

### Backend

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --app-dir backend
```

Alternatively:

```powershell
cd backend
..\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Backend URLs:

- API root: <http://127.0.0.1:8000/>
- Health: <http://127.0.0.1:8000/api/health>
- Swagger API docs: <http://127.0.0.1:8000/api/docs>
- Docs alias: <http://127.0.0.1:8000/docs>

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open the URL shown by Vite, normally <http://localhost:5173>.

## API Examples

### Health

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

A healthy local response includes:

```json
{
  "status": "healthy",
  "database": "disabled (local knowledge base)",
  "llm_configured": true
}
```



### Search

```powershell
$body = @{ query = "fourth amendment regulations"; top_k = 5 } | ConvertTo-Json

Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/search `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

## Project Structure

```text
backend/
  app/
    api/                    FastAPI routes
    services/classification  Intent and entity extraction
    services/llm/            Prompting and LLM provider
    services/rag/            RAG orchestration
    services/retrieval/      Local PDF loading and retrieval
    schemas/                 Request and response models
frontend/
  src/
    App.jsx                 Chat application shell
    components/             Chat message and citation UI
    services/api.js          Backend API client
scripts/                     Utility scripts
frontend/*.pdf               Indexed BIS knowledge documents
```

