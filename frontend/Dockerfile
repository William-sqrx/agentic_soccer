# ── Frontend – React (Create React App) ────────────────────────────────────
# Stage 1: build the production bundle
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY public/ public/
COPY src/ src/

# REACT_APP_API_URL is baked in at build time.
# Pass it with: docker build --build-arg REACT_APP_API_URL=http://localhost:8000
ARG REACT_APP_API_URL=http://localhost:8000
ENV REACT_APP_API_URL=$REACT_APP_API_URL

RUN npm run build

# Stage 2: serve with a lightweight nginx
FROM nginx:alpine

COPY --from=builder /app/build /usr/share/nginx/html

# Simple nginx config that routes all requests to index.html (SPA)
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
