# Stage 1: Build the Next.js app
FROM node:18 AS builder

WORKDIR /app

# Copy package.json and package-lock.json
COPY package*.json ./

# Install dependencies
RUN npm install -g npm@10 && npm install

# Copy the rest of the application code
COPY . .

# Set build arguments and ensure HTTPS
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=https://${NEXT_PUBLIC_API_URL}

# Build the application
RUN npm run build

# Stage 2: Serve the Next.js app with Nginx
FROM nginx:alpine AS nginx

# Remove default Nginx website
RUN rm -rf /usr/share/nginx/html/*

# Copy build output to Nginx public directory
COPY --from=builder /app/out /usr/share/nginx/html

# Copy custom Nginx configuration file
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80