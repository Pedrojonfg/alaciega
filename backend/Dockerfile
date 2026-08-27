# syntax=docker/dockerfile:1
# Build context: repository root (see docker-compose.yml).

ARG LC0_REF=v0.31.2

FROM python:3.12-bookworm AS lc0
ARG LC0_REF
RUN apt-get update && apt-get install -y --no-install-recommends \
        git gcc g++ meson ninja-build pkg-config cmake \
        libeigen3-dev zlib1g-dev python3 \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --recurse-submodules --branch "$LC0_REF" --depth 1 \
        https://github.com/LeelaChessZero/lc0.git /src/lc0
WORKDIR /src/lc0
# ponytail: flags must exist on lc0 v0.31.2; Eigen BLAS, no GPU
RUN meson setup build --buildtype=release \
        -Ddefault_library=static \
        -Dblas=true -Dopenblas=false -Dmkl=false -Ddnnl=false -Daccelerate=false \
        -Dplain_cuda=false -Dcudnn=false -Dopencl=false -Ddx=false \
        -Dgtest=false -Dispc=false \
    && meson compile -C build

FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl libstdc++6 zlib1g libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=lc0 /src/lc0/build/lc0 /usr/local/bin/lc0
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY scripts/download_maia_weights.sh scripts/entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/download_maia_weights.sh /usr/local/bin/entrypoint.sh \
    && mkdir -p /app/data /app/weights
ENV LC0_PATH=/usr/local/bin/lc0 \
    MAIA_WEIGHTS_DIR=/app/weights \
    DATABASE_PATH=/app/data/alaciega.db
EXPOSE 8000
ENTRYPOINT ["entrypoint.sh"]
