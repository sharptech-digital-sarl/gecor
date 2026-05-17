FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_URL=http://localhost:8000/api/v1
ENV VITE_API_URL=$VITE_API_URL
ARG VITE_LOGO_FILE=default.svg
ENV VITE_LOGO_FILE=$VITE_LOGO_FILE
ARG VITE_LOGO_MONOGRAM=
ENV VITE_LOGO_MONOGRAM=$VITE_LOGO_MONOGRAM
ARG VITE_APP_VERSION=1.0
ENV VITE_APP_VERSION=$VITE_APP_VERSION

RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY docker/nginx-default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
