FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -L -o /tmp/xray.zip \
    https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip \
    && unzip /tmp/xray.zip -d /usr/local/bin/xray \
    && chmod +x /usr/local/bin/xray/xray \
    && rm /tmp/xray.zip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .
COPY config.json /etc/xray/config.json

ENV PYTHONUNBUFFERED=1

EXPOSE 8081

CMD ["sh", "-c", "/usr/local/bin/xray/xray run -config /etc/xray/config.json & exec python bot.py"]