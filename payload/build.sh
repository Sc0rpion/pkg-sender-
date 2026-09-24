#!/bin/sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Normalize timestamps to prevent "Clock skew detected" warnings (e.g. in WSL2 / Docker)
find . -type f -exec touch {} + 2>/dev/null || true

usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  (no args)    Build PS5 payload ELF (requires PS5_PAYLOAD_SDK)"
    echo "  --host       Build native Linux test binary (pkg-receiver-host)"
    echo "  --docker     Build PS5 ELF using Docker (isolated, no dependencies needed)"
    echo "  --clean      Clean build artifacts"
    echo "  --help       Show this help message"
    exit 0
}

case "$1" in
    --help|-h)
        usage
        ;;
    --clean)
        echo "Cleaning build artifacts..."
        make clean
        exit 0
        ;;
    --host)
        echo "Building native host binary (pkg-receiver-host)..."
        make host
        echo "Build successful: $SCRIPT_DIR/pkg-receiver-host"
        exit 0
        ;;
    --docker)
        echo "Building PS5 payload with Docker..."
        docker build -t ps5-receiver-builder .
        docker run --rm -v "$SCRIPT_DIR":/out ps5-receiver-builder sh -c "make && cp pkg-receiver.elf /out/"
        echo "Build successful: $SCRIPT_DIR/pkg-receiver.elf"
        exit 0
        ;;
    *)
        if [ -z "$PS5_PAYLOAD_SDK" ]; then
            if [ -d "/opt/ps5-payload-sdk" ]; then
                export PS5_PAYLOAD_SDK=/opt/ps5-payload-sdk
                echo "Using detected SDK at: $PS5_PAYLOAD_SDK"
            else
                echo "Error: PS5_PAYLOAD_SDK environment variable is not set."
                echo ""
                echo "Options:"
                echo "  1) Set the SDK path: export PS5_PAYLOAD_SDK=/path/to/ps5-payload-sdk"
                echo "  2) Build using Docker: $0 --docker"
                echo "  3) Build host test binary: $0 --host"
                exit 1
            fi
        fi
        echo "Building PS5 payload ELF using $PS5_PAYLOAD_SDK..."
        make
        echo "Build successful: $SCRIPT_DIR/pkg-receiver.elf"
        ;;
esac
