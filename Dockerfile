# ---------------------
# BACKEND (.NET Build)
# ---------------------
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS backend

WORKDIR /code
COPY OpenBullet2/ .
RUN dotnet publish OpenBullet2.Web/OpenBullet2.Web.csproj -c Release -o /build/web

# ---------------------
# FRONTEND (Angular)
# ---------------------
FROM node:20 AS frontend

WORKDIR /code
COPY OpenBullet2/openbullet2-web-client/package.json .
COPY OpenBullet2/openbullet2-web-client/package-lock.json .
RUN npm ci

COPY OpenBullet2/openbullet2-web-client .
RUN npm run build
RUN mkdir /build && mv dist/* /build

# ---------------------
# AGGREGATE (Runtime)
# ---------------------
FROM mcr.microsoft.com/dotnet/aspnet:8.0

ENV DEBIAN_FRONTEND=noninteractive
ENV ASPNETCORE_URLS=http://0.0.0.0:${PORT:-10000}

WORKDIR /app

COPY --from=backend /build/web .
COPY --from=frontend /build ./wwwroot
COPY OpenBullet2/OpenBullet2.Web/dbip-country-lite.mmdb .

EXPOSE 10000

ENTRYPOINT ["dotnet", "OpenBullet2.Web.dll", "--urls=http://0.0.0.0:10000"]
