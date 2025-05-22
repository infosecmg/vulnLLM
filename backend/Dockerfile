# 1. Base Image
# Using an official Python slim image for a smaller footprint.
# Python 3.10 is a good general choice for many ML libraries currently.
FROM python:3.13.3-slim

# 2. Set Environment Variables
# Prevents Python from buffering stdout and stderr, making logs appear in Cloud Run more quickly.
ENV PYTHONUNBUFFERED=TRUE
# Sets the default port the application inside the container will listen on.
# Cloud Run will map its external port to this internal port.
# Recommended by Hugging Face to disable progress bars during model downloads in non-interactive environments.
ENV HF_HUB_DISABLE_PROGRESS_BARS=1
# Disable pip cache to reduce image size slightly.
ENV PIP_NO_CACHE_DIR=off
ENV PORT=8080
# 3. Set Working Directory
# All subsequent commands (COPY, RUN, CMD) will be relative to this directory.
WORKDIR /app

# 4. Copy Requirements File
# Copy only the requirements file first to leverage Docker's layer caching.
# If requirements.txt doesn't change, this layer won't be rebuilt, speeding up subsequent builds.
COPY requirements.txt .

# 5. Install Dependencies
# Install Python packages specified in requirements.txt.
# --no-cache-dir reduces image size by not storing the pip download cache.
# --prefer-binary can speed up installation for packages that have pre-compiled wheels.
RUN pip3 install --no-cache-dir --prefer-binary -r requirements.txt

# 6. Copy Application Code
# Copy your main.py (or any other application modules) into the WORKDIR.
COPY ./LLM_Backend.py /app/LLM_Backend.py
# If you had other Python modules or directories (e.g., a 'utils' folder), you would copy them here as well.
# e.g., COPY ./utils /app/utils

# 7. Expose Port
# Informs Docker that the container listens on the specified network port at runtime.
# This is more for documentation; Cloud Run uses the PORT env variable primarily.
EXPOSE 8080

# 8. Define the Command to Run the Application
# This is the command that will be executed when the container starts.
# It starts the Uvicorn ASGI server to run your FastAPI application.
# "--host", "0.0.0.0" makes the server accessible from outside the container.
# "--port", "${PORT}" tells Uvicorn to listen on the port specified by the PORT environment variable.
# "--workers", "1" is often recommended for Cloud Run with CPU-bound tasks like ML inference
# to avoid issues with multi-processing and shared resources, especially with Hugging Face models.
# You can adjust the number of workers based on testing and the nature of your workload.
CMD ["uvicorn", "LLM_Backend:app", "--host", "0.0.0.0", "--port", "8080"]
