# Trello Crew Playground

Small Python playground that:

1. Polls a Trello board.
2. When a new card appears in `In Progress`, it reads the card requirement.
3. Runs a 3-agent CrewAI workflow.
4. Posts the result back to Trello.
5. Moves the card to `Done`.

## What it does

- `Web Researcher` fetches and analyzes web pages (when URLs are in the card).

The workflow processes tasks in sequence: Analyst → Web Researcher → Writer → Reviewer.

## Files

- `app.py` - FastAPI app with a poll loop and health endpoints
- `trello_crew_playground/settings.py` - all configuration in one place
- `trello_crew_playground/trello_client.py` - Trello API wrapper
- `trello_crew_playground/workflow.py` - CrewAI workflow
 `trello_crew_playground/tools.py` - Web scraping and analysis tools

## Setup
## Web Scraping & Analysis

The Web Researcher agent automatically handles tasks involving web pages without requiring curl or command-line tools. For example:
### Prerequisites
**Trello Card Description:**
```
Go to https://axonivy-market.github.io/market-monitor/ and check how many repos are mentioned
```

**What happens:**
1. The Analyst reads the card and identifies this as a web research task
2. The Web Researcher automatically fetches the URL and analyzes the page
3. Available tools:
	- `fetch_webpage(url)` - Fetches page content and extracts text
	- `extract_links(url)` - Lists all hyperlinks on a page
	- `extract_repositories(text)` - Identifies GitHub-style repository references (owner/repo)
4. The Writer incorporates findings into a professional document
5. The Reviewer polishes it for Trello
**For Local LLM (Ollama):**
1. Install [Ollama](https://ollama.ai)
2. Pull a model (e.g., `ollama pull mistral` or `ollama pull llama2`)
3. Start Ollama: `ollama serve` (runs on `http://localhost:11434` by default)
4. The app uses Ollama through its OpenAI-compatible endpoint at `http://localhost:11434/v1`

**For Cloud LLM (OpenAI - optional fallback):**
- Set `USE_LOCAL_LLM=false` in `.env` to use OpenAI instead
- Requires `OPENAI_API_KEY`

### Installation

1. Create a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in your Trello credentials.
4. Configure LLM settings in `.env`:

```env
# Use local Ollama (recommended)
USE_LOCAL_LLM=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# Or use OpenAI (legacy)
USE_LOCAL_LLM=false
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4o-mini
```

5. Enable CrewAI by setting:

```env
USE_CREWAI=true
```

6. Start the app:

```bash
uvicorn app:app --reload
```

## How it works

- The app checks your Trello board on a fixed interval.
- It looks for cards whose current list is `In Progress`.
- If a card has not already been processed, the workflow runs once.
- The result is added as a Trello comment or saved to a file, then the card is moved to `Done`.

## Notes

- The app resolves list names from the board, so you can keep list names in config instead of hardcoding IDs.
- The first version writes the generated document to a local Markdown file and also posts a concise Trello comment.
