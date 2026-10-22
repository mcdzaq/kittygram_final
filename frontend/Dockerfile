FROM node:22-bookworm-slim AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN CI=true npm run build

# This one-shot container publishes the built files into the shared volume.
FROM busybox:1.37.0
WORKDIR /app
COPY --from=build /app/build ./build
CMD ["sh", "-c", "cp -r /app/build/. /static/"]
