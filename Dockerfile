FROM python:3.11-slim

# Install system dependencies
# LibreOffice for PDF conversion (python-docx -> PDF)
# poppler-utils for pdf2image
# fonts-nanum, fonts-noto-cjk for Korean support
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    libreoffice-writer \
    poppler-utils \
    fonts-nanum \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files first (for layer caching)
COPY pyproject.toml uv.lock ./

# Install Python dependencies using uv with cache mount
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# Copy application code
COPY . .

# Install project in editable mode
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -e .

# Run the bot
CMD ["python", "-u", "bot/main.py"]
