FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
LABEL org.jarvis.deerflow-runtime="1"
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core espeak-ng \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /opt/requirements.txt
COPY resolved-requirements.txt /opt/resolved-requirements.txt
RUN pip install --no-cache-dir -r /opt/resolved-requirements.txt
ENV MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib PYTHONDONTWRITEBYTECODE=1 \
    OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2
USER 65534:65534
WORKDIR /mnt/user-data/workspace
CMD ["sleep", "infinity"]
