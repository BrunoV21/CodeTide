FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies (if any are needed, add here)
# RUN apt-get update && apt-get install -y <dependencies> && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the code
COPY . .

# Install the package (so entry points are available)
RUN pip install -e .

# Default command: launch the CLI
ENTRYPOINT ["codetide-cli"]
