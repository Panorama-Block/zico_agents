#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

ORIGINAL_USER=$(stat -c '%U' .)
ORIGINAL_GROUP=$(stat -c '%G' .)

create_ssl_dir() {
    if [ ! -d "frontend/ssl" ]; then
        echo -e "${GREEN}Creating SSL directory...${NC}"
        mkdir -p frontend/ssl
    fi
}

create_self_signed_cert() {
    echo -e "${GREEN}Generating self-signed certificates...${NC}"
    create_ssl_dir
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout frontend/ssl/privkey.pem \
        -out frontend/ssl/fullchain.pem \
        -subj "/CN=localhost" 2>/dev/null
}

copy_production_certs() {
    echo -e "${GREEN}Copying production certificates...${NC}"
    create_ssl_dir
    if [ -f "/etc/letsencrypt/live/zico.panoramablock.com/fullchain.pem" ]; then
        cp /etc/letsencrypt/live/zico.panoramablock.com/fullchain.pem frontend/ssl/
        cp /etc/letsencrypt/live/zico.panoramablock.com/privkey.pem frontend/ssl/
        chmod 644 frontend/ssl/*
    else
        echo -e "${RED}Production certificates not found!${NC}"
        return 1
    fi
}

fix_permissions() {
    chown -R $ORIGINAL_USER:$ORIGINAL_GROUP .
}

main() {
    if [ "$1" = "prod" ]; then
        ENV_FILE=".env.prod"
        CERT_FUNC=copy_production_certs
    else
        ENV_FILE=".env.local"
        CERT_FUNC=create_self_signed_cert
    fi

    echo -e "${GREEN}Configuring environment with $ENV_FILE...${NC}"
    cp "$ENV_FILE" .env
    cp "$ENV_FILE" frontend/.env
    
    $CERT_FUNC
    
    fix_permissions
    
    echo -e "${GREEN}Restarting containers...${NC}"
    if [ "$EUID" -eq 0 ]; then
        su - $ORIGINAL_USER -c "cd $(pwd) && docker compose down"
        su - $ORIGINAL_USER -c "cd $(pwd) && docker compose up --build -d"
    else
        docker compose down
        docker compose up --build -d
    fi

    echo -e "${GREEN}Configuration complete!${NC}"
}

if [ "$1" = "prod" ] || [ "$1" = "dev" ] || [ -z "$1" ]; then
    main "$1"
else
    echo -e "${RED}Usage: $0 [dev|prod]${NC}"
    exit 1
fi