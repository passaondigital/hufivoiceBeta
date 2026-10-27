FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HUFIVOICE_CONFIG=/opt/hufivoice/deploy/config-online.json

WORKDIR /opt/hufivoice
COPY app ./app
COPY web ./web
COPY deploy/config-online.json ./deploy/config-online.json

USER 65532:65532
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=2)"

CMD ["python3", "app/hufivoice_web.py", "--host", "0.0.0.0", "--port", "8765", "--rate-limit", "30", "--parallel", "2"]
