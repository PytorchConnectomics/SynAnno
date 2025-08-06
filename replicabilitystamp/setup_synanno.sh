#!/bin/bash

APP_NAME="synanno-app"
CONTAINER_NAME="synanno-container"

# Function to clone, build, and run the SynAnno application
function run_app() {
    echo "Cloning and building SynAnno..."
    if [ ! -d "SynAnno" ]; then
        git clone https://github.com/PytorchConnectomics/SynAnno.git
    fi
    cd SynAnno || exit 1

    echo "Building Docker image ($APP_NAME)..."
    docker build -t "$APP_NAME" -f Dockerfile_uwsgi .

    echo "Running Docker container ($CONTAINER_NAME) on port 80..."
    docker run -d --rm \
        -p 80:80 -p 9015:9015 \
        --name "$CONTAINER_NAME" \
        "$APP_NAME"

    sleep 5
    echo "Opening SynAnno in your browser at http://localhost/demo"
    open http://localhost/demo 2>/dev/null || xdg-open http://localhost/demo
}

# Function to stop and clean up the Docker container and image
function cleanup() {
    echo "Stopping and removing Docker container (if running)..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || echo "Container not running."

    echo "Removing Docker image..."
    docker rmi "$APP_NAME"
}

# Handle command-line arguments
case "$1" in
    "")
        run_app
        ;;
    cleanup)
        cleanup
        ;;
    help|-h|--help)
        echo "Usage: bash setup_synanno.sh [cleanup]"
        echo ""
        echo "  (no args)   Set up and run SynAnno"
        echo "  cleanup     Stop container and remove image"
        ;;
    *)
        echo "Unknown argument: $1"
        echo "Run with 'help' for usage."
        ;;
esac
