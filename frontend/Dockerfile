FROM node:20-alpine AS builder

WORKDIR /app

# VITE_API_URL is injected at build time so the React bundle knows
# where to reach the backend (e.g. https://insightiq-backend.railway.app)
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

COPY package.json .
RUN npm install

COPY . .
RUN npm run build

# ── Production image ──────────────────────────────────────────────────────────
FROM nginx:alpine

# Install envsubst (part of gettext) so we can substitute $PORT in nginx.conf
RUN apk add --no-cache gettext

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/templates/default.conf.template

# Railway sets $PORT dynamically. This entrypoint substitutes it into nginx.conf
# then starts nginx.
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80
ENTRYPOINT ["/entrypoint.sh"]
