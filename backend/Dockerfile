# ── Backend – Flask + LangGraph agent + Wine (for PAT3.Console.exe) ────────
#
# Based on docker-wine so the Python backend can invoke PAT3 via Wine.
FROM scottyhardy/docker-wine:latest

# ── Install Python 3.11 via deadsnakes PPA ─────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3.11-dev python3-pip unzip \
    && rm -rf /var/lib/apt/lists/*

# Make python3.11 the default python/python3
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python  python  /usr/bin/python3.11 1

# ── Install PAT3 ───────────────────────────────────────────────────────────
COPY MONO-PAT-v3.6.0.zip /pat/MONO-PAT-v3.6.0.zip
RUN unzip /pat/MONO-PAT-v3.6.0.zip -d /pat \
    && rm /pat/MONO-PAT-v3.6.0.zip \
    && chmod -R 777 /pat

# ── Python dependencies ────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application source ─────────────────────────────────────────────────────
COPY app.py graph.py main.py state.py ./
COPY tools/ ./tools/
COPY model/ ./model/

# The pcsp_model/ and data/processed/ directories are mounted at runtime
# via docker-compose volumes.  tools/ and model/ are also bind-mounted
# during development so edits on the host are reflected immediately.

ENV PYTHONUNBUFFERED=1
# Tell pat_runner.py where PAT3 lives and that it must be invoked via Wine
ENV PAT_PATH=/pat/MONO-PAT-v3.6.0/PAT3.Console.exe
ENV PAT_USE_WINE=1

EXPOSE 8000

# Override docker-wine's entrypoint; we only need Wine as a callable binary,
# not the interactive desktop/audio setup that the default entrypoint provides.
ENTRYPOINT []
CMD ["python", "main.py"]
