# Stage 1: Build
FROM python:3.13-slim as builder

# Install uv directly from astral's official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Enable bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1

# Create a virtual environment and place it in the PATH
RUN uv venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies without development tools (frozen locks versions)
RUN uv sync --frozen --no-dev --no-install-project

# Stage 2: Runtime
FROM python:3.13-slim as runtime

WORKDIR /app

# Copy the isolated virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only the source code to keep the image strictly minimal
COPY src/ /app/src/

# Create a non-root user for security best practices
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Start the application
CMD ["fastapi", "run", "src/main.py", "--host", "0.0.0.0", "--port", "8000"]
