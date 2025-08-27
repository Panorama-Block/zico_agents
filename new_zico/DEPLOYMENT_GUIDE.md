# Zico Multi-Agent System - VM Deployment Guide

This guide provides step-by-step instructions for deploying the Zico Multi-Agent System on a virtual machine (VM).

## 📋 Prerequisites

### System Requirements
- **OS**: Ubuntu 20.04 LTS or later (recommended)
- **RAM**: Minimum 4GB, recommended 8GB+
- **Storage**: Minimum 20GB free space
- **CPU**: 2+ cores recommended
- **Network**: Stable internet connection

### Required Accounts
- Google Cloud account with Gemini API access
- GitHub account (if using private repository)

## 🚀 Step-by-Step Deployment

### Step 1: VM Setup and Initial Configuration

#### 1.1 Update System Packages
```bash
sudo apt update && sudo apt upgrade -y
```

#### 1.2 Install Essential Tools
```bash
sudo apt install -y curl wget git unzip software-properties-common apt-transport-https ca-certificates gnupg lsb-release
```

#### 1.3 Install Python 3.11+ and pip
```bash
# Add deadsnakes PPA for Python 3.11
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Set Python 3.11 as default
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# Upgrade pip
python3 -m pip install --upgrade pip
```

### Step 2: Install System Dependencies

#### 2.1 Install Build Dependencies
```bash
sudo apt install -y build-essential libssl-dev libffi-dev python3-dev
```

#### 2.2 Install Additional System Libraries
```bash
sudo apt install -y libpq-dev libjpeg-dev libpng-dev libgif-dev libwebp-dev
```

### Step 3: Clone and Setup Project

#### 3.1 Clone Repository
```bash
# Navigate to home directory
cd ~

# Clone the repository (replace with your actual repository URL)
git clone <your-repository-url> zico_agent
cd zico_agent/new_zico
```

#### 3.2 Create Virtual Environment
```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Verify Python version
python --version  # Should show Python 3.11.x
```

### Step 4: Install Python Dependencies

#### 4.1 Install Requirements
```bash
# Upgrade pip in virtual environment
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

#### 4.2 Verify Installation
```bash
# Test if key packages are installed
python -c "import fastapi, uvicorn, langchain, langgraph; print('All packages installed successfully')"
```

### Step 5: Environment Configuration

#### 5.1 Create Environment File
```bash
# Create .env file
cat > .env << EOF
# Gemini API Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-pro
GEMINI_EMBEDDING_MODEL=models/embedding-001

# Application Configuration
MAX_UPLOAD_LENGTH=16777216
MAX_CONVERSATION_LENGTH=100
MAX_CONTEXT_MESSAGES=10

# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=False

# Database Configuration (optional for production)
DATABASE_URL=sqlite:///./zico_agent.db

# Redis Configuration (optional for caching)
REDIS_URL=redis://localhost:6379

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=/var/log/zico_agent/app.log
EOF
```

#### 5.2 Set Up API Key
```bash
# Edit the .env file to add your actual Gemini API key
nano .env
```

**Important**: Replace `your_gemini_api_key_here` with your actual Google Gemini API key.

### Step 6: Database Setup (Optional for Production)

#### 6.1 Install PostgreSQL (Recommended for Production)
```bash
# Install PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Start and enable PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql -c "CREATE DATABASE zico_agent;"
sudo -u postgres psql -c "CREATE USER zico_user WITH PASSWORD 'your_secure_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE zico_agent TO zico_user;"
```

#### 6.2 Update Database URL in .env
```bash
# Update .env file with PostgreSQL URL
sed -i 's|DATABASE_URL=sqlite:///./zico_agent.db|DATABASE_URL=postgresql://zico_user:your_secure_password@localhost/zico_agent|' .env
```

### Step 7: Redis Setup (Optional for Caching)

#### 7.1 Install Redis
```bash
# Install Redis
sudo apt install -y redis-server

# Start and enable Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Test Redis connection
redis-cli ping  # Should return PONG
```

### Step 8: Create System Service

#### 8.1 Create Application Directory
```bash
# Create application directory
sudo mkdir -p /opt/zico_agent
sudo chown $USER:$USER /opt/zico_agent

# Copy application files
cp -r ~/zico_agent/new_zico/* /opt/zico_agent/
```

#### 8.2 Create Systemd Service File
```bash
sudo tee /etc/systemd/system/zico-agent.service > /dev/null << EOF
[Unit]
Description=Zico Multi-Agent System
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/zico_agent
Environment=PATH=/opt/zico_agent/.venv/bin
ExecStart=/opt/zico_agent/.venv/bin/uvicorn src.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

#### 8.3 Enable and Start Service
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable zico-agent

# Start service
sudo systemctl start zico-agent

# Check status
sudo systemctl status zico-agent
```

### Step 9: Nginx Setup (Reverse Proxy)

#### 9.1 Install Nginx
```bash
sudo apt install -y nginx
```

#### 9.2 Create Nginx Configuration
```bash
sudo tee /etc/nginx/sites-available/zico-agent > /dev/null << EOF
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeout settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Static files (if any)
    location /static/ {
        alias /opt/zico_agent/static/;
        expires 30d;
    }
}
EOF
```

#### 9.3 Enable Site and Restart Nginx
```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/zico-agent /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

### Step 10: SSL Certificate Setup (Optional but Recommended)

#### 10.1 Install Certbot
```bash
sudo apt install -y certbot python3-certbot-nginx
```

#### 10.2 Obtain SSL Certificate
```bash
# Replace with your actual domain
sudo certbot --nginx -d your-domain.com
```

### Step 11: Firewall Configuration

#### 11.1 Configure UFW Firewall
```bash
# Enable UFW
sudo ufw enable

# Allow SSH
sudo ufw allow ssh

# Allow HTTP and HTTPS
sudo ufw allow 80
sudo ufw allow 443

# Allow application port (if not using Nginx)
sudo ufw allow 8000

# Check status
sudo ufw status
```

### Step 12: Monitoring and Logging Setup

#### 12.1 Create Log Directory
```bash
sudo mkdir -p /var/log/zico_agent
sudo chown $USER:$USER /var/log/zico_agent
```

#### 12.2 Install Monitoring Tools
```bash
# Install htop for system monitoring
sudo apt install -y htop

# Install logrotate for log management
sudo apt install -y logrotate
```

#### 12.3 Create Logrotate Configuration
```bash
sudo tee /etc/logrotate.d/zico-agent > /dev/null << EOF
/var/log/zico_agent/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
}
EOF
```

### Step 13: Testing the Deployment

#### 13.1 Test Application Health
```bash
# Test health endpoint
curl http://localhost:8000/health

# Test chat endpoint
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "role": "user",
      "content": "Hello, how are you?"
    },
    "conversation_id": "test123",
    "user_id": "test_user"
  }'
```

#### 13.2 Test Nginx Proxy
```bash
# Test through Nginx
curl http://your-domain.com/health
```

### Step 14: Backup and Maintenance Setup

#### 14.1 Create Backup Script
```bash
cat > /opt/zico_agent/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/zico_agent"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup application files
tar -czf $BACKUP_DIR/zico_agent_$DATE.tar.gz /opt/zico_agent

# Backup database (if using PostgreSQL)
pg_dump zico_agent > $BACKUP_DIR/database_$DATE.sql

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete

echo "Backup completed: $DATE"
EOF

chmod +x /opt/zico_agent/backup.sh
```

#### 14.2 Setup Automated Backups
```bash
# Add to crontab for daily backups at 2 AM
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/zico_agent/backup.sh") | crontab -
```

## 🔧 Troubleshooting

### Common Issues and Solutions

#### 1. Service Won't Start
```bash
# Check service logs
sudo journalctl -u zico-agent -f

# Check if port is in use
sudo netstat -tlnp | grep :8000

# Restart service
sudo systemctl restart zico-agent
```

#### 2. API Key Issues
```bash
# Test API key
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('API Key:', os.getenv('GEMINI_API_KEY')[:10] + '...' if os.getenv('GEMINI_API_KEY') else 'Not found')
"
```

#### 3. Database Connection Issues
```bash
# Test PostgreSQL connection
psql -h localhost -U zico_user -d zico_agent -c "SELECT 1;"
```

#### 4. Memory Issues
```bash
# Check memory usage
free -h

# Check swap
swapon --show
```

## 📊 Monitoring Commands

### System Monitoring
```bash
# Check system resources
htop

# Check disk usage
df -h

# Check memory usage
free -h

# Check running processes
ps aux | grep zico
```

### Application Monitoring
```bash
# Check service status
sudo systemctl status zico-agent

# Check logs
sudo journalctl -u zico-agent -f

# Check Nginx status
sudo systemctl status nginx

# Check Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## 🔄 Update and Maintenance

### Updating the Application
```bash
# Stop service
sudo systemctl stop zico-agent

# Backup current version
/opt/zico_agent/backup.sh

# Pull latest changes
cd /opt/zico_agent
git pull origin main

# Update dependencies
source .venv/bin/activate
pip install -r requirements.txt

# Start service
sudo systemctl start zico-agent
```

### Regular Maintenance Tasks
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Clean old logs
sudo find /var/log -name "*.log" -mtime +30 -delete

# Check disk space
df -h

# Check for security updates
sudo unattended-upgrades --dry-run
```

## 📞 Support and Documentation

### Useful Commands
```bash
# Restart all services
sudo systemctl restart zico-agent nginx

# Check all service statuses
sudo systemctl status zico-agent nginx postgresql redis-server

# View real-time logs
sudo journalctl -u zico-agent -f

# Test API endpoints
curl -X GET http://localhost:8000/health
```

### Configuration Files Location
- Application: `/opt/zico_agent/`
- Environment: `/opt/zico_agent/.env`
- Service: `/etc/systemd/system/zico-agent.service`
- Nginx: `/etc/nginx/sites-available/zico-agent`
- Logs: `/var/log/zico_agent/`

## ✅ Deployment Checklist

- [ ] VM setup and system updates completed
- [ ] Python 3.11+ installed and configured
- [ ] Project cloned and virtual environment created
- [ ] Dependencies installed successfully
- [ ] Environment variables configured
- [ ] Database setup completed (if using)
- [ ] Redis setup completed (if using)
- [ ] Systemd service created and enabled
- [ ] Nginx configured and enabled
- [ ] SSL certificate obtained (if applicable)
- [ ] Firewall configured
- [ ] Monitoring and logging setup completed
- [ ] Backup system configured
- [ ] Application tested and working
- [ ] Health checks passing

## 🎉 Deployment Complete!

Your Zico Multi-Agent System is now deployed and running on your VM. The application should be accessible at:
- Local: `http://localhost:8000`
- External: `http://your-domain.com` (if configured)

For production deployments, consider implementing:
- Load balancing for high availability
- Database clustering for scalability
- Advanced monitoring with Prometheus/Grafana
- CI/CD pipeline for automated deployments
- Security hardening and regular audits 