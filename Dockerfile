# ---------------------
# BACKEND (.NET Build)
# ---------------------
FROM mcr.microsoft.com/dotnet/sdk:10.0-noble AS backend

WORKDIR /code
COPY OpenBullet2/ ./OpenBullet2/
RUN dotnet publish OpenBullet2/OpenBullet2.Web/OpenBullet2.Web.csproj -c Release -o /build/web

WORKDIR /build/web
RUN find . -name "*.xml" -type f -delete
RUN cp /code/OpenBullet2/OpenBullet2.Web/dbip-country-lite.mmdb /build/

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
RUN mkdir /build && mv dist/* /build

# ---------------------
# AGGREGATE (Runtime)
# ---------------------
FROM mcr.microsoft.com/dotnet/aspnet:10.0-noble

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

COPY --from=backend /build/web .
COPY --from=frontend /build ./wwwroot
COPY OpenBullet2/OpenBullet2.Web/dbip-country-lite.mmdb .

EXPOSE 10000

ENTRYPOINT ["dotnet", "OpenBullet2.Web.dll", "--urls=http://0.0.0.0:10000"]
