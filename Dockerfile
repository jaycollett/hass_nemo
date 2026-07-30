# syntax=docker/dockerfile:1.7
#
# NeMo WFST text normalization is CPU-only (pynini/OpenFST) - no GPU or
# PyTorch base image needed. A slim Python base cuts the image from ~20GB to
# ~2GB.
#
# Kept on Debian (glibc) rather than Alpine: pynini ships manylinux x86_64
# wheels only, and building OpenFST against musl is not a fight worth having
# for a CVE pass. Raised python:3.11-slim -> python:3.13-slim-trixie; pynini
# 2.1.6.post1 does publish a cp313 wheel.
#
# Two stages: the builder holds gcc/g++ (needed to compile cdifflib, which is
# source-only), the runtime stage receives only the finished virtualenv.
#
# This image is linux/amd64 only, because pynini is.

# ---- Stage 1: build the virtualenv ----
FROM python:3.13-slim-trixie AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv

# Pinned dependencies for reproducible builds. pynini is pinned to the exact
# version nemo_text_processing requires.
RUN pip install --no-cache-dir \
    nemo_text_processing==1.2.0 \
    pynini==2.1.6.post1 \
    flask==3.1.1 \
    gunicorn==23.0.0

# ---- Stage 2: runtime ----
FROM python:3.13-slim-trixie

# Grammar cache: mount a volume here to skip the slow grammar build on restart.
ENV CACHE_DIR=/cache \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# libstdc++ (already present in the base) backs pynini's OpenFST extension; no
# compilers and no apt lists are carried into this layer.

COPY --from=builder /opt/venv /opt/venv

COPY nemo_api.py /app/nemo_api.py
COPY preprocess.py /app/preprocess.py
COPY default_rules.json /app/default_rules.json
WORKDIR /app

# /cache holds the compiled grammars; /config is where users mount their own
# preprocess_rules.json (single-file mount). Both must be writable by the
# non-root runtime user.
RUN groupadd --gid 1000 nemo \
    && useradd --uid 1000 --gid 1000 --no-create-home --shell /usr/sbin/nologin nemo \
    && mkdir -p /cache /config \
    && chown -R nemo:nemo /cache /config /app

USER 1000:1000

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=4)" || exit 1

# Single worker (each worker loads the full grammar set into memory),
# threads for concurrent requests, generous timeout for long texts.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "300", "nemo_api:app"]
