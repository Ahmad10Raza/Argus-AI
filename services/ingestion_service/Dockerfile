FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for caching
COPY services/ingestion_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared libraries
COPY libs /app/libs

# Copy service code
COPY services/ingestion_service /app/services/ingestion_service

# Set python path to include root
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "services.ingestion_service.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
