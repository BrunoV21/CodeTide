# Use the official Python 3.12 image
FROM python:3.13-alpine

# Set the working directory
WORKDIR /app

# Install required system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create the /app/files directory and set full permissions
RUN mkdir -p /app/.files && chmod 777 /app/.files
RUN mkdir -p /app/logs && chmod 777 /app/logs
RUN mkdir -p /app/observability_data && chmod 777 /app/observability_data
RUN mkdir -p /app/storage && chmod 777 /app/storage
RUN mkdir -p /app/sessions && chmod 777 /app/sessions

# Copy the current repository into the container
COPY . /app

# Upgrade pip and install dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

EXPOSE 7860

CMD uvicorn api:app --host 0.0.0.0 --port 7860
