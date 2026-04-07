FROM scottyhardy/docker-wine:latest

# Copy and unzip PAT
COPY backend/MONO-PAT-v3.6.0.zip /pat/MONO-PAT-v3.6.0.zip
RUN apt-get update && apt-get install -y unzip \
    && unzip /pat/MONO-PAT-v3.6.0.zip -d /pat \
    && rm /pat/MONO-PAT-v3.6.0.zip \
    && chmod -R 777 /pat

# Copy PCSP model
COPY pcsp_model/football_pressure.pcsp /pat/football_pressure.pcsp

ENTRYPOINT ["/usr/bin/entrypoint"]

# Development: open bash shell
# Production: replace with your python backend e.g. CMD ["python3", "main.py"]
CMD ["bash"]
