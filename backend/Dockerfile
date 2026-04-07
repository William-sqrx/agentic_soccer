# ── Backend – Flask + LangGraph agent ──────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer-cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source (everything except venv, cache, etc.)
COPY app.py graph.py main.py state.py ./

# The tools/, model/, pcsp_model/, and data/processed/ directories are
# mounted at runtime via docker-compose volumes so the agent can reach them.

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "main.py"]
