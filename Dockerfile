# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY dashboard/requirements.txt dashboard/
COPY data_engine/requirements.txt data_engine/

# Install Python dependencies
RUN pip install --no-cache-dir -r dashboard/requirements.txt

# Copy the entire dashboard and data_engine application
COPY dashboard/ dashboard/
COPY data_engine/ data_engine/

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8080

# Run the application with gunicorn from the dashboard directory
WORKDIR /app/dashboard
CMD exec gunicorn --bind :$PORT --workers 2 --threads 4 --timeout 0 dash_app:server
