# OpenBullet2 - Render Deployment

Minimalistyczny projekt deploy'ujący OpenBullet2.Web na Render Web Services.

## Lokalne uruchomienie

```bash
git clone --recursive https://github.com/dynamite-ai-coder/Test.git
cd Test
docker compose up --build
```

Aplikacja dostępna pod adresem: `http://localhost:10000`

## Deploy na Render

### Automatyczny (via render.yaml)
1. Fork/Zaimportuj repozytorium na GitHub
2. W Render Dashboard kliknij **New > Web Service**
3. Połącz repozytorium GitHub
4. Render automatycznie wykryje `render.yaml` i skonfiguruje serwis

### Ręczny
1. W Render Dashboard kliknij **New > Web Service**
2. Połącz repozytorium GitHub
3. Ustaw:
   - **Runtime**: Docker
   - **Port**: 10000
4. Kliknij **Create Web Service**

Po deployu aplikacja będzie dostępna pod adresem:
```
https://<service-name>.onrender.com
```

## Struktura projektu

```
Test/
├── OpenBullet2/          # Submodule z OpenBullet2
├── Dockerfile            # Dockerfile dla Render
├── render.yaml           # Konfiguracja Render
├── .dockerignore         # Pliki ignorowane przez Docker
└── README.md
```

## Uwagi
- Render Free Plan ma ograniczenia (spinning down after inactivity)
-首次启动 może potrwać kilka minut (budowanie obrazu Docker)
- Dla produkcji zalecany jest plan Starter lub wyższy
