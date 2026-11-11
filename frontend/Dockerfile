FROM node:22-alpine

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

ARG VITE_PORT=5173
ENV VITE_PORT=${VITE_PORT}
EXPOSE ${VITE_PORT}
CMD ["npm", "run", "dev"]
