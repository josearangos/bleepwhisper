ARG PYTHON_IMAGE=python:3.11.18-slim-trixie@sha256:82209229d3fda30d71e603ec95bb4bea0476635ba6df3df2e32284e036654f51

FROM ${PYTHON_IMAGE} AS builder
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY requirements.lock /build/requirements.lock
RUN pip install --no-cache-dir --require-hashes --no-deps -r /build/requirements.lock
COPY pyproject.toml README.md /build/
COPY src/ /build/src/
RUN pip install --no-cache-dir --no-deps /build && chmod -R a+rX /opt/venv

FROM builder AS model
ARG WHISPER_MODEL=small
ENV HF_HOME=/opt/hf
RUN python -c "from faster_whisper import download_model; download_model('${WHISPER_MODEL}')" \
    && chmod -R a+rX /opt/hf

FROM ${PYTHON_IMAGE} AS runtime
ARG WHISPER_MODEL=small
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 bleeper \
    && useradd --uid 1000 --gid 1000 --create-home bleeper
COPY --from=builder /opt/venv /opt/venv
COPY --from=model /opt/hf /opt/hf
RUN mkdir -p /var/lib/bleeper \
    && chown 1000:1000 /var/lib/bleeper
ENV PATH=/opt/venv/bin:$PATH \
    HF_HOME=/opt/hf \
    HF_HUB_OFFLINE=1 \
    BLEEPER_MODEL=${WHISPER_MODEL} \
    BLEEPER_UI_HOST=0.0.0.0 \
    BLEEPER_UI_PORT=7860 \
    BLEEPER_UI_MAX_UPLOAD_MB=100 \
    BLEEPER_UI_DATA=/var/lib/bleeper \
    GRADIO_ANALYTICS_ENABLED=False \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
LABEL org.opencontainers.image.source="https://github.com/josearangos/bleepwhisper" \
      org.opencontainers.image.version="0.1.0" \
      bleeper.whisper-model="${WHISPER_MODEL}"
USER 1000:1000
WORKDIR /home/bleeper
ENTRYPOINT ["bleeper"]
CMD ["--help"]
