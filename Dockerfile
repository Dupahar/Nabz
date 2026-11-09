# Nabz web app. Built by AWS CodeBuild (deploy/buildspec.yml) and run on AWS App Runner (HTTPS).
FROM public.ecr.aws/docker/library/python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY deploy/requirements-prod.txt /app/deploy/requirements-prod.txt
RUN pip install --no-cache-dir -r /app/deploy/requirements-prod.txt

COPY app /app/app
COPY tools /app/tools
COPY lenses /app/lenses
COPY config /app/config
COPY deploy /app/deploy

# Container filesystems are ephemeral on App Runner: data lives in /data and is seeded on start with
# the synthetic demo visits (deploy/seed). Real uploads persist only until the next deploy.
ENV NABZ_DATA_DIR=/data PYTHONUNBUFFERED=1 PORT=8080
RUN useradd --create-home nabz && mkdir -p /data && chown nabz /data
USER nabz
EXPOSE 8080
CMD ["sh", "/app/deploy/start.sh"]
