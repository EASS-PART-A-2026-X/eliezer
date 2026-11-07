# Ollama for CPUs: the official release archive, without its GPU libraries.
#
# The official image (ollama/ollama) is about 3.4 GB compressed because it ships
# CUDA for NVIDIA GPUs. This image keeps only what CPU inference needs. On a
# machine with an NVIDIA GPU, use the official image instead (see the README).
#
# To upgrade: change OLLAMA_VERSION and both checksums, copied from
# https://github.com/ollama/ollama/releases/download/v<version>/sha256sum.txt

FROM debian:trixie-slim AS download
ARG OLLAMA_VERSION=0.40.15
ARG SHA256_amd64=628c018404a4206493efd38e46251c154ede5141b8b8dc85c659b3b027c47379
ARG SHA256_arm64=7f699ead5cdb4ae1ed89b888b148a238af188708800871e1889ab9dcee95f247
ARG TARGETARCH
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl zstd \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /tmp
# One step, so the 1.5 GB archive never ends up in an image layer.
RUN set -eu; \
    file="ollama-linux-${TARGETARCH}.tar.zst"; \
    curl -fsSLo "$file" \
        "https://github.com/ollama/ollama/releases/download/v${OLLAMA_VERSION}/${file}"; \
    eval "sha=\$SHA256_${TARGETARCH}"; \
    echo "${sha}  ${file}" | sha256sum -c -; \
    mkdir /out; \
    zstd -dc "$file" | tar -x -C /out \
        --wildcards --exclude='*cuda*' --exclude='*rocm*' --exclude='*vulkan*'; \
    rm "$file"; \
    /out/bin/ollama --version || true

FROM debian:trixie-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# bin/ollama and lib/ollama, laid out as the official installer does.
COPY --from=download /out/ /usr/
# A non-root user; /models becomes the volume that keeps downloaded models.
RUN useradd --uid 10001 --create-home ollama \
    && mkdir /models \
    && chown ollama /models
# Serves, and downloads the model named in AI_MODEL the first time.
COPY --chmod=755 entrypoint.sh /usr/local/bin/ollama-start
USER ollama
ENV OLLAMA_HOST=0.0.0.0:11434 \
    OLLAMA_MODELS=/models
EXPOSE 11434
ENTRYPOINT ["ollama-start"]
