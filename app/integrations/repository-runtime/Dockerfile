# Reviewed dependency-only runtime. Repository packages are never installed here.
FROM python:3.13-slim@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c
LABEL org.jarvis.repository-runtime="1"
COPY requirements.txt /runtime-requirements.txt
RUN python -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r /runtime-requirements.txt
USER 65534:65534
WORKDIR /work
