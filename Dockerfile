# NeMo WFST text normalization is CPU-only (pynini/OpenFST) - no GPU or
# PyTorch base image needed. Slim Python base cuts the image from ~20GB to ~2GB.
FROM python:3.11-slim

# Pinned dependencies for reproducible builds.
# pynini is pinned to the exact version nemo_text_processing requires; it only
# ships x86_64 Linux wheels, so this image is linux/amd64 only.
# gcc/g++ are needed to compile cdifflib (source-only dist) and are removed
# in the same layer to keep the image small.
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && \
    pip install --no-cache-dir \
    nemo_text_processing==1.2.0 \
    pynini==2.1.6.post1 \
    flask==3.1.1 \
    gunicorn==23.0.0 && \
    apt-get purge -y gcc g++ && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# Grammar cache: mount a volume here to skip the slow grammar build on restart.
ENV CACHE_DIR=/cache
RUN mkdir -p /cache

# /config is where users mount their own preprocess_rules.json (single-file mount).
RUN mkdir -p /config

COPY nemo_api.py /app/nemo_api.py
COPY preprocess.py /app/preprocess.py
COPY default_rules.json /app/default_rules.json
WORKDIR /app

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=4)" || exit 1

# Single worker (each worker loads the full grammar set into memory),
# threads for concurrent requests, generous timeout for long texts.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "300", "nemo_api:app"]
