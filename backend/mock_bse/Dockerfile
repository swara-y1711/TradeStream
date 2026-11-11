FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ARG MOCK_BSE_PORT=8001
ENV MOCK_BSE_PORT=${MOCK_BSE_PORT}
ARG MOCK_BSE_HOST=0.0.0.0
ENV MOCK_BSE_HOST=${MOCK_BSE_HOST}
EXPOSE ${MOCK_BSE_PORT}
CMD ["sh", "-c", "uvicorn app:app --host $MOCK_BSE_HOST --port $MOCK_BSE_PORT"]
