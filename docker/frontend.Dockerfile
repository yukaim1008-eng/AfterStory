FROM node:24-alpine AS build

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
COPY data/character-assets/ /build/data/character-assets/
COPY data/design-reference/ /build/data/design-reference/
COPY 背景/ /build/背景/
RUN npm run build

FROM nginx:stable-alpine
COPY docker/web.conf /etc/nginx/conf.d/default.conf
COPY --from=build /build/frontend/dist/ /usr/share/nginx/html/
EXPOSE 80
