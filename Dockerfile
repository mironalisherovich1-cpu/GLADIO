# Python 3.11 operatsion tizimining engil versiyasi
FROM python:3.11-slim

# asyncpg va boshqa kutubxonalar build bo'lishi uchun kerakli tizim paketlari
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Ishchi papka
WORKDIR /app

# Kutubxonalarni o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Barcha fayllarni nusxalash
COPY . .

# Botni ishga tushirish (Procfile o'rniga ishlaydi)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
