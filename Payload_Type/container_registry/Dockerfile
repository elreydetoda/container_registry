FROM python:3.11-slim

# Install skopeo and other dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    skopeo \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /Mythic/

# Copy payload type files
COPY . /Mythic/

# Install Python dependencies
RUN pip install --no-cache-dir mythic-container==0.3.4

# Set the entrypoint
CMD ["python3", "main.py"]
