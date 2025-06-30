FROM --platform=linux/amd64 python:3.10-bullseye

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file first for better caching
COPY requirements.txt .

RUN mkdir -p /app/ssl && chmod 755 /app/ssl

# Install system dependencies and optimize memory usage during installation
RUN apt-get update && \
    apt-get install -y gcc g++ procps && \
    # Install Python dependencies with optimized settings and retry options
    python3 -m pip install --no-cache-dir --upgrade pip && \
    python3 -m pip install --no-cache-dir --upgrade setuptools wheel && \
    # Install dependencies with retry options and timeout settings
    pip install --no-cache-dir --timeout 100 --retries 10 -r requirements.txt && \
    # Clean up apt cache
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

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
RUN apt-get install -y chromium chromium-driver && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set environment variables for Chrome
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_BIN=/usr/bin/chromedriver

# Copy the application files
COPY . .

# Expose the port your application listens on
EXPOSE 8080

# Run the application using uvicorn without SSL for development
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8080"]

## Run the application using uvicorn with SSL support
#CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8080", "--ssl-keyfile", "/app/ssl/privkey.pem", "--ssl-certfile", "/app/ssl/fullchain.pem"]