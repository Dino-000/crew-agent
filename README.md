# Trello Crew Playground

Small Python playground that:

1. Polls a Trello board.
2. When a new card appears in `In Progress`, it reads the card requirement.
3. Runs a 3-agent CrewAI workflow.
4. Posts the result back to Trello.
5. Moves the card to `Done`.

## What it does

- `Analyst` extracts the real requirement from the card.
- `Writer` creates the training document draft.
- `Reviewer` improves and validates the result.
- The app layer orchestrates the workflow and handles Trello updates.

## Files

- `app.py` - FastAPI app with a poll loop and health endpoints
- `trello_crew_playground/settings.py` - all configuration in one place
- `trello_crew_playground/trello_client.py` - Trello API wrapper
- `trello_crew_playground/workflow.py` - CrewAI workflow
- `trello_crew_playground/state_store.py` - simple local processed-card state

## Setup

1. Create a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in values.
4. Start the app:

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
