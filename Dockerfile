FROM python:3.11-slim

# libraries for google earth engine and image processing
RUN apt-get update && apt-get install -y \
    binutils \
    libproj-dev \
    gdal-bin \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

#change and add maybe a single router for when you make more scripts for diff things... worry abt later 
CMD ["python", "map_correlation.py"]