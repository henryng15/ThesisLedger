#!/bin/bash
set -e

# Setup Ollama container with required models
# Pulls llama3.2:3b (inference) and nomic-embed-text (embeddings)
#
# Usage:
#   ./scripts/setup_ollama.sh                    # Use defaults
#   ./scripts/setup_ollama.sh --llm-model llama2 # Custom LLM model
#   ./scripts/setup_ollama.sh --host 0.0.0.0     # Custom host
#   ./scripts/setup_ollama.sh --wait 60           # Custom wait timeout

set_defaults() {
    OLLAMA_HOST="${OLLAMA_HOST:-localhost}"
    OLLAMA_PORT="${OLLAMA_PORT:-11434}"
    LLM_MODEL="${LLM_MODEL:-llama3.2:3b}"
    EMBED_MODEL="${EMBED_MODEL:-nomic-embed-text}"
    WAIT_TIMEOUT="${WAIT_TIMEOUT:-120}"
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --host)
                OLLAMA_HOST="$2"
                shift 2
                ;;
            --port)
                OLLAMA_PORT="$2"
                shift 2
                ;;
            --llm-model)
                LLM_MODEL="$2"
                shift 2
                ;;
            --embed-model)
                EMBED_MODEL="$2"
                shift 2
                ;;
            --wait)
                WAIT_TIMEOUT="$2"
                shift 2
                ;;
            *)
                echo "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
    done
}

print_usage() {
    cat << EOF
Setup Ollama with required models for ThesisLedger.

Usage: ./scripts/setup_ollama.sh [OPTIONS]

Options:
  --host HOST               Ollama host (default: localhost)
  --port PORT               Ollama port (default: 11434)
  --llm-model MODEL         LLM model to pull (default: llama3.2:3b)
  --embed-model MODEL       Embedding model to pull (default: nomic-embed-text)
  --wait SECONDS            Max seconds to wait for Ollama (default: 120)
  --help                    Show this help message

Examples:
  ./scripts/setup_ollama.sh
  ./scripts/setup_ollama.sh --llm-model llama2 --embed-model all-minilm
  ./scripts/setup_ollama.sh --host 0.0.0.0 --port 11434
EOF
}

wait_for_ollama() {
    local host=$1
    local port=$2
    local timeout=$3
    local elapsed=0
    local interval=2

    echo "⏳ Waiting for Ollama to be ready (${timeout}s timeout)..."
    while [ $elapsed -lt $timeout ]; do
        if curl -s "http://${host}:${port}/api/tags" > /dev/null 2>&1; then
            echo "✓ Ollama is ready"
            return 0
        fi
        echo "  Waiting... ($((elapsed + interval))s elapsed)"
        sleep $interval
        elapsed=$((elapsed + interval))
    done

    echo "✗ Ollama failed to start within ${timeout}s"
    return 1
}

pull_model() {
    local model=$1
    local host=$2
    local port=$3

    echo "📦 Pulling model: $model"
    if curl -s "http://${host}:${port}/api/pull" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"$model\", \"stream\": false}" > /dev/null 2>&1; then
        echo "✓ Successfully pulled $model"
        return 0
    else
        echo "✗ Failed to pull $model"
        return 1
    fi
}

verify_models() {
    local host=$1
    local port=$2

    echo "🔍 Verifying installed models..."
    if curl -s "http://${host}:${port}/api/tags" | grep -q "name"; then
        curl -s "http://${host}:${port}/api/tags" | grep '"name"' | sed 's/.*"name": "\([^"]*\)".*/  ✓ \1/'
        return 0
    else
        echo "✗ Failed to verify models"
        return 1
    fi
}

main() {
    set_defaults
    parse_args "$@"

    if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
        print_usage
        exit 0
    fi

    echo "🚀 ThesisLedger Ollama Setup"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Host:           ${OLLAMA_HOST}"
    echo "Port:           ${OLLAMA_PORT}"
    echo "LLM Model:      ${LLM_MODEL}"
    echo "Embed Model:    ${EMBED_MODEL}"
    echo ""

    # Wait for Ollama container to be ready
    if ! wait_for_ollama "$OLLAMA_HOST" "$OLLAMA_PORT" "$WAIT_TIMEOUT"; then
        echo ""
        echo "💡 Tip: Start Ollama with:"
        echo "   docker compose --profile with-ollama up -d ollama"
        exit 1
    fi

    # Pull models
    echo ""
    echo "📥 Pulling models..."
    if ! pull_model "$LLM_MODEL" "$OLLAMA_HOST" "$OLLAMA_PORT"; then
        exit 1
    fi

    if ! pull_model "$EMBED_MODEL" "$OLLAMA_HOST" "$OLLAMA_PORT"; then
        exit 1
    fi

    # Verify
    echo ""
    verify_models "$OLLAMA_HOST" "$OLLAMA_PORT"

    echo ""
    echo "✅ Ollama setup complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Update your .env file:"
    echo "     OLLAMA_BASE_URL=http://${OLLAMA_HOST}:${OLLAMA_PORT}"
    echo "     OLLAMA_LLM_MODEL=${LLM_MODEL}"
    echo "     OLLAMA_EMBED_MODEL=${EMBED_MODEL}"
    echo ""
    echo "  2. Start the Django backend:"
    echo "     cd backend && python manage.py runserver"
    echo ""
}

main "$@"
