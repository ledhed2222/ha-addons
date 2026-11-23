FROM ghcr.io/ledhed2222/anki-sync-mcp:0.2.0-oauth.2

USER root
COPY run.py /run.py
# The base image's check needs the server's settings, which only run.py's child process has.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=4)"]
CMD ["python", "/run.py"]
