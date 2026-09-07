# Telegram Bot - TMLog Search

Bot Telegram do wyszukiwania danych logowania (login:pass) dla podanych domen za pośrednictwem API tmlogbot.

## Funkcje

- Wyszukiwanie danych logowania dla wielu domen
- Automatyczne zapisywanie wyników jako pliki .txt
- Informacja o liczbie linii w znalezionych plikach
- Wysyłanie plików bezpośrednio w Telegramie

## Konfiguracja

1. Skopiuj `.env.example` do `.env`
2. Uzupełnij zmienne środowiskowe:

```
BOT_TOKEN=token_od_BotFather
TMLOG_API_URL=https://tmlogbot.com/api
TMLOG_LOGIN=twoj_login
TMLOG_PASS=twoje_haslo
```

## Uruchomienie lokalne

```bash
pip install -r requirements.txt
python bot.py
```

## Deploy na Render

1. Załóż konto na [render.com](https://render.com)
2. Utwórz nowy Worker
3. Połącz repozytorium GitHub
4. Render automatycznie wykryje `render.yaml`
5. Uzupełnij zmienne środowiskowe w panelu Render:
   - `BOT_TOKEN` - token bota Telegram
   - `TMLOG_LOGIN` - login do tmlogbot
   - `TMLOG_PASS` - hasło do tmlogbot
6. Deploy nastąpi automatycznie

## Użycie

1. Otwórz bota w Telegramie
2. Wyślij `/start`
3. Wklej listę domen (po jednej w linii):
```
example.com
example2.com
example3.com
```
4. Bot wyśle pliki .txt z danymi logowania dla każdej domeny

## Zmienne środowiskowe

| Zmienna | Opis |
|---------|------|
| `BOT_TOKEN` | Token bota Telegram (od @BotFather) |
| `TMLOG_API_URL` | URL API tmlogbot |
| `TMLOG_LOGIN` | Login do tmlogbot |
| `TMLOG_PASS` | Hasło do tmlogbot |
