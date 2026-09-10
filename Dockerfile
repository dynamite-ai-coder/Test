# ---------------------
# BACKEND (.NET Build)
# ---------------------
FROM mcr.microsoft.com/dotnet/sdk:10.0-noble AS backend

WORKDIR /code
# Copy only the necessary files for the backend build to leverage caching
COPY OpenBullet2/ ./OpenBullet2/
RUN dotnet publish OpenBullet2/OpenBullet2.Web/OpenBullet2.Web.csproj -c Release -o /build/web

# ---------------------
# FRONTEND (Angular)
# ---------------------
FROM node:20.9.0 AS frontend

WORKDIR /code
COPY OpenBullet2/openbullet2-web-client/package.json .
COPY OpenBullet2/openbullet2-web-client/package-lock.json .
RUN npm install

COPY OpenBullet2/openbullet2-web-client .
RUN npm run build
# The output of 'ng build' with "outputPath": "dist" in angular.json goes directly into dist/
RUN mkdir /build && cp -r dist/* /build

# ---------------------
# AGGREGATE (Runtime)
# ---------------------
FROM mcr.microsoft.com/dotnet/aspnet:10.0-noble

ENV DEBIAN_FRONTEND=noninteractive
# Set default port to 10000 if not provided by Render
ENV PORT=10000

WORKDIR /app

COPY --from=backend /build/web .
COPY --from=frontend /build ./wwwroot
# Ensure the mmdb file is present (it should be copied by dotnet publish, but this is a safeguard)
COPY OpenBullet2/OpenBullet2.Web/dbip-country-lite.mmdb .

EXPOSE 10000

# Use CMD to allow Render to inject the PORT environment variable
CMD ["sh", "-c", "dotnet OpenBullet2.Web.dll --urls http://0.0.0.0:${PORT}"]
