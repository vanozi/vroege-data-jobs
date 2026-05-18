FROM mcr.microsoft.com/playwright/python:v1.57.0-noble

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml .
COPY main.py .
COPY .env .

# Install dependencies
RUN uv sync --all-extras

# Run the main.py script
CMD ["uv", "run", "python", "main.py"]
