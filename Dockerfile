FROM --platform=$BUILDPLATFORM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY fetch.py /app/fetch.py

RUN useradd -u 1000 -m runner && mkdir -p /data && chown runner:runner /data
USER runner

VOLUME ["/data"]
ENTRYPOINT ["python", "/app/fetch.py"]
CMD ["--out", "/data"]
