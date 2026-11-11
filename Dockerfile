# API de inferência (#24) empacotada para execução reproduzível (#28).
#
# Variante padrão: backend simulado (`.[api]`), sem pesos e sem PyTorch.
# Variante real: --build-arg EXTRAS=api,vision (PyTorch CPU; imagem grande).
# A imagem NÃO contém tokens, certificados, pesos, vídeos nem resultados:
# tudo isso entra por volumes somente leitura (veja compose.yaml).

ARG PYTHON_IMAGE=python:3.12-slim

FROM ${PYTHON_IMAGE} AS build
ARG EXTRAS=api
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /src
COPY pyproject.toml ./
COPY src ./src
RUN python -m venv /opt/venv \
    && case ",${EXTRAS}," in \
         *,vision,*) /opt/venv/bin/pip install torch torchvision --index-url "${TORCH_INDEX}" ;; \
       esac \
    && /opt/venv/bin/pip install ".[${EXTRAS}]"

FROM ${PYTHON_IMAGE} AS runtime
ARG EXTRAS=api
# Bibliotecas de sistema exigidas pelo OpenCV apenas na variante com visão.
RUN case ",${EXTRAS}," in \
      *,vision,*) apt-get update \
                  && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
                  && rm -rf /var/lib/apt/lists/* ;; \
    esac \
    && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin sonar
COPY --from=build /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp \
    YOLO_CONFIG_DIR=/tmp/ultralytics
USER sonar
EXPOSE 8443
# Certificado, chave e CA vêm de /run/sonar/tls (volume). O host 0.0.0.0 vale só
# dentro do contêiner; a publicação da porta em loopback é feita no Compose.
ENTRYPOINT ["python", "-m", "sonar_vision_api", "--host", "0.0.0.0", \
            "--certfile", "/run/sonar/tls/server.pem", \
            "--keyfile", "/run/sonar/tls/server-key.pem"]
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-m", "sonar_vision_api.healthcheck", "--cafile", "/run/sonar/tls/ca.pem"]
