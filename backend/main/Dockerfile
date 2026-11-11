FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ARG BACKEND_PORT=8000
ENV BACKEND_PORT=${BACKEND_PORT}
ARG BACKEND_HOST=0.0.0.0
ENV BACKEND_HOST=${BACKEND_HOST}
EXPOSE ${BACKEND_PORT}
CMD ["sh", "-c", "uvicorn app:app --host $BACKEND_HOST --port $BACKEND_PORT"]
