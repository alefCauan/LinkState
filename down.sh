#!/bin/bash 

# This script is used to stop the docker containers and remove the network
# Usage: ./down.sh


if [ ! -f docker-compose.yml ]; then
    echo "Error: docker-compose.yml not found in the current directory"
    exit 1
fi

docker compose down --remove-orphans || { echo "Error: Failed to stop containers"; exit 1; }
docker network prune -f || { echo "Error: Failed to prune networks"; exit 1; }
