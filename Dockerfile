# SafePlate orchestrator, keyless rules mode, for a free container host.
# Gemma 4 E2B is a 7.2 GB model run on a laptop through Ollama, so this image
# ships no model: the hosted service hears typed text by keyword matching and
# answers in fixed sentences. The safety decisions are the same code either way.
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SAFEPLATE_MODE=rules \
    PORT=8000

WORKDIR /app

RUN useradd --create-home --uid 10001 safeplate

COPY requirements.txt .
RUN pip install -r requirements.txt

# serp.py resolves its cache as <project root>/fixtures/serp, where the project
# root is the parent of the safeplate package, so /app/fixtures/serp here. The
# cached SerpApi answers must ship: they let the lookup run with no key set.
COPY safeplate/ ./safeplate/
COPY fixtures/serp/ ./fixtures/serp/

# The service user owns the cache so a keyed lookup can add to it at runtime.
RUN chown -R safeplate:safeplate /app/fixtures

USER safeplate

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn safeplate.api:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
