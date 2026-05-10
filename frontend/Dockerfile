# --- build stage ---
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build

# --- runtime stage ---
FROM nginx:1.27-alpine

# Static SPA
COPY --from=build /app/dist /usr/share/nginx/html

# Nginx config template (BACKEND_URL substituted at container start)
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Default backend URL (override via env var BACKEND_URL at runtime)
ENV BACKEND_URL="http://localhost:8000"
ENV PORT=8080
# Limit envsubst to ONLY our two variables so nginx-native vars like $host,
# $remote_addr, $scheme, $proxy_add_x_forwarded_for in the template are not
# replaced with empty strings.
ENV NGINX_ENVSUBST_FILTER="^(BACKEND_URL|PORT)$"

EXPOSE 8080

# nginx:alpine includes envsubst and runs /etc/nginx/templates/*.template
# automatically through /docker-entrypoint.d/ scripts; just hand off to the
# default entrypoint.
CMD ["nginx", "-g", "daemon off;"]
