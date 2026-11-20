FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY control_tower/ control_tower/
COPY scripts/ scripts/
COPY tests/ tests/
COPY examples/ examples/
RUN mkdir /data && chown 10001:10001 /data
USER 10001:10001
CMD ["python", "scripts/jarvis_network.py", "--help"]
