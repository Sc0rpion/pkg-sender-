# Dockerfile to build PS5 PKG Receiver payload
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    clang \
    llvm \
    lld \
    git \
    python3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Clone and install PS5 Payload SDK
RUN git clone --depth 1 https://github.com/ps5-payload-dev/sdk.git /tmp/ps5-payload-sdk \
    && cd /tmp/ps5-payload-sdk \
    && make \
    && make install DESTDIR=/opt/ps5-payload-sdk \
    && rm -rf /tmp/ps5-payload-sdk

ENV PS5_PAYLOAD_SDK=/opt/ps5-payload-sdk

WORKDIR /src
COPY . .
RUN find /src -type f -exec touch {} + 2>/dev/null || true

CMD ["make"]
