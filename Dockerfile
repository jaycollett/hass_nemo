# Base image with NVIDIA support for PyTorch
FROM nvcr.io/nvidia/pytorch:23.01-py3

# Install system dependencies for Pynini and OpenFST
RUN apt-get update && apt-get install -y \
    libfst-dev \
    g++ \
    curl \
    git \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install nemo-toolkit pynini

# Copy the NeMo API script into the container
COPY nemo_api.py /app/nemo_api.py
WORKDIR /app

# Expose port for the API
EXPOSE 5000

# Run the NeMo API server
CMD ["python", "nemo_api.py"]
