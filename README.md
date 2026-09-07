# Telegram Automation Queue System

System automatyzacji Telegram z dwoma botami: kontrolnym i klientem komunikującym się z botem docelowym.

## Wymagania

- Python 3.11+
- Telegram Bot Token (od @BotFather)
- Telegram API credentials (z https://my.telegram.org)

## Konfiguracja Telegram API

1. Utwórz bota kontrolnego przez @BotFather
2. Pobierz API credentials z https://my.telegram.org
3. Utwórz plik `.env` na podstawie `.env.example`

## Instalacja

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edytuj .env z swoimi danymi
```

## Uruchomienie

```bash
python main.py
```

Pierwsze uruchomienie poprosi o autoryzację Telegram (kod SMS).

## Użycie bota

### Komendy
- `/start` - Menu główne z przyciskami
- `/add <url>` - Dodaj URL do kolejki
- `/addlist` - Dodaj listę URLi
- `/queue` - Pokaż kolejkę
- `/status` - Status systemu
- `/pause` - Wstrzymaj worker
- `/resume` - Wznów worker
- `/stop` - Zatrzymaj worker
- `/clear` - Wyczyść kolejkę

### Przyciski inline
- ➕ Add URL - Dodaj URL
- 📋 Queue - Pokaż kolejkę
- ▶️ Start - Uruchom worker
- ⏸ Pause - Wstrzymaj
- ⏹ Stop - Zatrzymaj
- 📊 Status - Status systemu
- 🗑 Clear - Wyczyść kolejkę

## Queue states

- PENDING - Oczekuje na przetworzenie
- PROCESSING - W trakcie przetwarzania
- WAITING_FOR_RESPONSE - Oczekuje na odpowiedź bota
- WAITING_FOR_FILE - Oczekuje na plik
- COMPLETED - Zakończono
- FAILED - Niepowodzenie
- CANCELLED - Anulowano

## Deploy na Render

1. Wypchnij kod na GitHub
2. Utwórz nowy Background Worker na render.com
3. Ustaw zmienne środowiskowe
4. Deploy nastąpi automatycznie

## Docker

```bash
docker build -t telegram-automation .
docker run --env-file .env telegram-automation
```

## Security

- Tokeny API nigdy nie są commitowane do repo
- Tylko autoryzowani użytkownicy mogą kontrolować bota
- Walidacja plików przed zapisem
- sprawdzenie źródła plików
