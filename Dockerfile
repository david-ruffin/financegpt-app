# Stage 1: Build the React frontend
FROM node:20-slim AS builder

# Set working directory for frontend
WORKDIR /app/frontend

# Copy frontend package files
# Note: Assumes the frontend is in a subdirectory named 'project'
COPY project/package.json project/package-lock.json ./

# Install frontend dependencies
RUN npm install

# Copy the rest of the frontend source code
COPY project/ ./

# Build the frontend static files
RUN npm run build

# --- 

# Stage 2: Setup the Python backend and serve frontend
FROM python:3.11-slim

# Set working directory for backend
WORKDIR /app

# Install backend dependencies
COPY requirements.txt .
# Use --no-cache-dir to reduce image size
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY api_server.py .
# Add any other Python files/modules if they exist

# Copy built frontend static files from the builder stage
COPY --from=builder /app/frontend/dist /app/static

# Expose the port the app runs on (should match uvicorn command)
EXPOSE 8000

# Command to run the application using Uvicorn
# Use 0.0.0.0 to bind to all network interfaces within the container
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"] 