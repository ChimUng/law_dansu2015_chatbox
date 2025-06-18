# Use official Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies for underthesea and other libs
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    wget \
    git \
    python3-dev \
    python3-pip \
    libpq-dev \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libmariadb-dev \
    libmariadb-dev-compat \
    cmake \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Rust + maturin (for underthesea-core)
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
ENV PATH="/root/.cargo/bin:$PATH"
RUN pip install maturin

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Expose port
EXPOSE 8000

# Run the FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
