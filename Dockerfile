FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY agentroom/ agentroom/

RUN pip install --no-cache-dir .

EXPOSE 8765

VOLUME ["/data"]

ENV AGENTROOM_STATE_DIR=/data/agentroom

ENTRYPOINT ["agentctl", "serve", "--host", "0.0.0.0", "--port", "8765", "--state-dir", "/data/agentroom"]
