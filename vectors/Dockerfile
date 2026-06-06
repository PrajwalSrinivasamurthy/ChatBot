FROM python:3.11-slim

WORKDIR /app

# System deps for docx/image extraction
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir twilio httpx

COPY . .

# Create dirs that are volume-mounted at runtime
RUN mkdir -p static/images logs

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
