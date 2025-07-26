#!/bin/bash
# systemRecord Runner Script

set -e

# Default values
CONFIG_FILE=""
PROJECT_NAME=""
OUTPUT_DIR="./output"
DOCKER_MODE=false
VERBOSE=false

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS] PROJECT_NAME

systemRecord - System Fingerprinting Tool Runner

ARGUMENTS:
    PROJECT_NAME        Name for the project archive

OPTIONS:
    -c, --config FILE   Configuration file (required)
    -o, --output DIR    Output directory (default: ./output)
    -d, --docker        Run in Docker mode
    -v, --verbose       Enable verbose output
    -h, --help          Show this help message

EXAMPLES:
    # Local execution
    $0 -c config/default.yaml before_install
    
    # Docker execution
    $0 -d -c config/default.yaml -o /tmp/output after_install

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -d|--docker)
            DOCKER_MODE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        -*)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
        *)
            if [[ -z "$PROJECT_NAME" ]]; then
                PROJECT_NAME="$1"
            else
                echo "Too many arguments"
                show_usage
                exit 1
            fi
            shift
            ;;
    esac
done

# Validate required arguments
if [[ -z "$PROJECT_NAME" ]]; then
    echo "Error: PROJECT_NAME is required"
    show_usage
    exit 1
fi

if [[ -z "$CONFIG_FILE" ]]; then
    echo "Error: Configuration file is required (-c/--config)"
    show_usage
    exit 1
fi

# Check if config file exists
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Error: Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Get absolute paths
CONFIG_FILE=$(realpath "$CONFIG_FILE")
OUTPUT_DIR=$(realpath "$OUTPUT_DIR")

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Build command arguments
ARGS=("$PROJECT_NAME" "-c")

if [[ "$DOCKER_MODE" == true ]]; then
    # Docker execution
    echo "Running systemRecord in Docker mode..."
    echo "Project: $PROJECT_NAME"
    echo "Config: $CONFIG_FILE"
    echo "Output: $OUTPUT_DIR"
    
    DOCKER_ARGS=(
        "run" "--rm"
        "--user" "$(id -u):$(id -g)"
        "-v" "/:/system:ro"
        "-v" "$(dirname "$CONFIG_FILE"):/config:ro"
        "-v" "$OUTPUT_DIR:/output"
        "systemrecord"
        "$PROJECT_NAME"
        "-c" "/config/$(basename "$CONFIG_FILE")"
        "-o" "/output"
    )
    
    if [[ "$VERBOSE" == true ]]; then
        DOCKER_ARGS+=("-v")
    fi
    
    exec docker "${DOCKER_ARGS[@]}"
else
    # Local execution
    echo "Running systemRecord locally..."
    echo "Project: $PROJECT_NAME"
    echo "Config: $CONFIG_FILE"
    echo "Output: $OUTPUT_DIR"
    
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PYTHON_SCRIPT="$SCRIPT_DIR/src/main.py"
    
    if [[ ! -f "$PYTHON_SCRIPT" ]]; then
        echo "Error: systemRecord script not found: $PYTHON_SCRIPT"
        exit 1
    fi
    
    CMD_ARGS=(
        "$PYTHON_SCRIPT"
        "$PROJECT_NAME"
        "-c" "$CONFIG_FILE"
        "-o" "$OUTPUT_DIR"
    )
    
    if [[ "$VERBOSE" == true ]]; then
        CMD_ARGS+=("-v")
    fi
    
    exec python3 "${CMD_ARGS[@]}"
fi
