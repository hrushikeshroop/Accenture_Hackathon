FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Patch the run script to bind to 0.0.0.0 so ports are accessible from outside the container
RUN sed -i 's/127\.0\.0\.1/0.0.0.0/g' scripts/run_demo.py

# Expose Streamlit and API ports
EXPOSE 8501 8000

# Run the demo script
CMD ["python", "scripts/run_demo.py"]

