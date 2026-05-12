FROM python:3.10-slim

WORKDIR /app

COPY requirements-proxy.txt .
RUN pip install --no-cache-dir -r requirements-proxy.txt

COPY bot.py .

CMD ["python", "bot.py"]
