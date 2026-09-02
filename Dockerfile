# Use the official Microsoft Playwright image (includes Python and Chromium)
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Run both workers via start.sh
RUN chmod +x start.sh
CMD ["./start.sh"]
