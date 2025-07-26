# systemRecord Docker Image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Create output directory
RUN mkdir -p /app/output

# Create mount points for volumes
RUN mkdir -p /system /config /output

# Set executable permissions
RUN chmod +x src/main.py

# Create non-root user
RUN useradd -m -u 1000 systemrecord
RUN chown -R systemrecord:systemrecord /app
USER systemrecord

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Default command
ENTRYPOINT ["python", "src/main.py"]
CMD ["--help"]
