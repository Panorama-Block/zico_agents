FROM --platform=linux/amd64 python:3.10-bullseye

# Set the working directory in the container
WORKDIR /app

# Create SSL directory
RUN mkdir -p /app/ssl && chmod 755 /app/ssl

# Copy the requirements file first for better caching
COPY requirements.txt .

# Install system dependencies
RUN apt-get update && apt-get install -y gcc g++ procps && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --upgrade setuptools wheel && \
    pip install -r requirements.txt --no-deps --ignore-installed && \
    pip install -r requirements.txt

# Chrome installation for Debian Bullseye
RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    apt-transport-https \
    ca-certificates \
    unzip \
    xvfb \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm1

# Install ChromiumDriver instead of Chrome
RUN apt-get install -y chromium chromium-driver

# Set environment variables for Chrome
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_BIN=/usr/bin/chromedriver

COPY . .
COPY .env .env

# Expose both HTTP and HTTPS ports
EXPOSE 5000 5443

# Run the application using uvicorn with auto-reload enabled
CMD ["python3", "-m", "src.app"]