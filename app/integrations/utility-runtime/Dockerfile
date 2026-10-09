FROM python:3.13-slim@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c
LABEL org.jarvis.utility-runtime="1"
RUN apt-get update && apt-get install -y --no-install-recommends nmap && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir nbclient==0.11.0 nbformat==5.11.1 ipykernel==7.3.0
ENV HOME=/work JUPYTER_CONFIG_DIR=/work/config JUPYTER_DATA_DIR=/work/data JUPYTER_RUNTIME_DIR=/work/runtime IPYTHONDIR=/work/ipython
USER 65534:65534
WORKDIR /work
