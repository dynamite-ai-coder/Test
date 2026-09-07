#!/usr/bin/env python3

import time
import json
import threading
import urllib.request
import urllib.error

from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socketserver


# ============================================================
# CONFIG
# ============================================================

HOST = "127.0.0.1"
PORT = 8787

GROQ_URL = "https://api.groq.com/openai/v1"
MODEL = "groq/compound"

API_FILE = "api.txt"

# Bezpieczny lokalny limit kolejki.
# Proxy nie próbuje obchodzić limitów Groq.
SAFE_RPM = 25
SAFE_TPM = 7000
SAFE_RPD = 950
SAFE_TPD = 190000

MAX_COMPLETION_TOKENS = 4096

REQUEST_TIMEOUT = 600
MAX_RETRIES = 5


# ============================================================
# LOAD API KEYS
# ============================================================

def load_api_keys(filename=API_FILE):
    keys = []

    try:
        with open(filename, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if not line:
                    continue

                if line.startswith("#"):
                    continue

                if not line.startswith("apikey="):
                    continue

                key = line.split("=", 1)[1].strip()

                if key:
                    keys.append(key)

    except FileNotFoundError:
        print()
        print(f"ERROR: Nie znaleziono pliku: {filename}")
        print()
        print("Utwórz api.txt:")
        print("apikey=TWÓJ_KLUCZ")
        print("apikey=TWÓJ_KLUCZ")
        print()
        raise SystemExit(1)

    # Usuwanie duplikatów
    unique = []

    for key in keys:
        if key not in unique:
            unique.append(key)

    return unique


API_KEYS = load_api_keys()


# ============================================================
# KEY STATE
# ============================================================

class KeyState:

    def __init__(self, key, number):

        self.key = key
        self.number = number

        self.request_times = deque()
        self.token_times = deque()

        self.daily_requests = 0
        self.daily_tokens = 0

        self.day_start = time.time()

        self.cooldown_until = 0

        self.total_requests = 0
        self.total_tokens = 0
        self.total_429 = 0

        self.lock = threading.Lock()


    def reset_day(self):

        now = time.time()

        if now - self.day_start >= 86400:

            self.daily_requests = 0
            self.daily_tokens = 0
            self.day_start = now


    def cleanup(self):

        now = time.time()

        while (
            self.request_times
            and now - self.request_times[0] >= 60
        ):
            self.request_times.popleft()

        while (
            self.token_times
            and now - self.token_times[0][0] >= 60
        ):
            self.token_times.popleft()

        self.reset_day()


    def token_usage(self):

        return sum(
            amount
            for _, amount in self.token_times
        )


    def can_use(self, estimated_tokens):

        with self.lock:

            self.cleanup()

            now = time.time()

            if now < self.cooldown_until:
                return False

            if self.daily_requests >= SAFE_RPD:
                return False

            if (
                self.daily_tokens + estimated_tokens
                >= SAFE_TPD
            ):
                return False

            if len(self.request_times) >= SAFE_RPM:
                return False

            if (
                self.token_usage() + estimated_tokens
                >= SAFE_TPM
            ):
                return False

            return True


    def reserve(self, estimated_tokens):

        with self.lock:

            self.cleanup()

            now = time.time()

            self.request_times.append(now)

            self.token_times.append(
                (now, estimated_tokens)
            )

            self.daily_requests += 1
            self.daily_tokens += estimated_tokens

            self.total_requests += 1
            self.total_tokens += estimated_tokens


    def cooldown(self, seconds):

        with self.lock:

            self.cooldown_until = max(
                self.cooldown_until,
                time.time() + seconds
            )

            self.total_429 += 1


    def info(self):

        with self.lock:

            self.cleanup()

            return {
                "key": self.number,

                "rpm": len(self.request_times),

                "tpm": self.token_usage(),

                "rpd": self.daily_requests,

                "tpd": self.daily_tokens,

                "cooldown": max(
                    0,
                    self.cooldown_until - time.time()
                ),

                "requests_total":
                    self.total_requests,

                "tokens_total":
                    self.total_tokens,

                "429_total":
                    self.total_429,
            }


# ============================================================
# INITIALIZE KEYS
# ============================================================

KEYS = [
    KeyState(key, index + 1)
    for index, key in enumerate(API_KEYS)
]


selection_lock = threading.Lock()
selection_index = 0


# ============================================================
# KEY SELECTION
# ============================================================

def select_key(estimated_tokens):

    global selection_index

    if not KEYS:
        return None

    with selection_lock:

        start = selection_index

        for offset in range(len(KEYS)):

            index = (
                start + offset
            ) % len(KEYS)

            candidate = KEYS[index]

            if candidate.can_use(
                estimated_tokens
            ):

                selection_index = (
                    index + 1
                ) % len(KEYS)

                return candidate

    return None


# ============================================================
# TOKEN ESTIMATION
# ============================================================

def estimate_tokens(body):

    try:

        data = json.loads(
            body.decode("utf-8")
        )

        compact = json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":")
        )

        input_tokens = max(
            1,
            len(compact) // 4
        )

        output_tokens = int(
            data.get(
                "max_completion_tokens",
                data.get(
                    "max_tokens",
                    MAX_COMPLETION_TOKENS
                )
            )
            or MAX_COMPLETION_TOKENS
        )

        output_tokens = min(
            output_tokens,
            MAX_COMPLETION_TOKENS
        )

        return input_tokens + output_tokens

    except Exception:

        return max(
            1,
            len(body) // 4
        )


# ============================================================
# NORMALIZE REQUEST
# ============================================================

def normalize(body):

    try:

        data = json.loads(
            body.decode("utf-8")
        )

    except Exception:

        return body

    if not isinstance(data, dict):
        return body

    # Wymuszamy model Groq
    data["model"] = MODEL

    # Ograniczenie outputu
    if "max_completion_tokens" in data:

        try:

            data["max_completion_tokens"] = min(
                int(data["max_completion_tokens"]),
                MAX_COMPLETION_TOKENS
            )

        except Exception:

            data["max_completion_tokens"] = (
                MAX_COMPLETION_TOKENS
            )

    elif "max_tokens" in data:

        try:

            data["max_tokens"] = min(
                int(data["max_tokens"]),
                MAX_COMPLETION_TOKENS
            )

        except Exception:

            data["max_tokens"] = (
                MAX_COMPLETION_TOKENS
            )

    else:

        data["max_completion_tokens"] = (
            MAX_COMPLETION_TOKENS
        )

    return json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":")
    ).encode("utf-8")


# ============================================================
# RETRY-AFTER
# ============================================================

def retry_after(headers):

    value = (
        headers.get("Retry-After")
        or headers.get("retry-after")
    )

    if value:

        try:
            return float(value)

        except ValueError:
            pass

    return None


# ============================================================
# GROQ REQUEST
# ============================================================

def groq_request(
    path,
    body,
    key_state,
    incoming_headers
):

    api_path = path
    if api_path.startswith("/v1"):
        api_path = api_path[3:]
    url = GROQ_URL + api_path

    headers = {
        "Authorization":
            "Bearer " + key_state.key,

        "Content-Type":
            incoming_headers.get(
                "Content-Type",
                "application/json"
            ),

        "Accept":
            incoming_headers.get(
                "Accept",
                "application/json"
            ),

        "User-Agent":
            "OpenCode-Groq-MultiKey-Proxy/1.0",
    }

    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method="POST"
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT
        ) as response:

            return (
                response.status,
                dict(response.headers),
                response.read()
            )

    except urllib.error.HTTPError as error:

        return (
            error.code,
            dict(error.headers),
            error.read()
        )

    except Exception as error:

        payload = {
            "error": {
                "type":
                    "proxy_connection_error",

                "message":
                    str(error)
            }
        }

        return (
            502,
            {},
            json.dumps(payload).encode()
        )


# ============================================================
# WAIT FOR AVAILABLE KEY
# ============================================================

def wait_for_key(estimated_tokens):

    start = time.time()

    while True:

        key = select_key(
            estimated_tokens
        )

        if key:

            key.reserve(
                estimated_tokens
            )

            return key

        # Maksymalny czas oczekiwania
        if time.time() - start > 900:

            raise TimeoutError(
                "All Groq keys are currently "
                "rate limited."
            )

        time.sleep(0.5)


# ============================================================
# HTTP HANDLER
# ============================================================

class Handler(BaseHTTPRequestHandler):

    protocol_version = "HTTP/1.1"

    allow_reuse_address = True


    def log_message(self, fmt, *args):

        print(
            "[proxy]",
            fmt % args
        )


    # --------------------------------------------------------
    # JSON RESPONSE
    # --------------------------------------------------------

    def send_json(
        self,
        status,
        payload
    ):

        data = json.dumps(
            payload,
            ensure_ascii=False
        ).encode()

        self.send_response(status)

        self.send_header(
            "Content-Type",
            "application/json"
        )

        self.send_header(
            "Content-Length",
            str(len(data))
        )

        self.send_header(
            "Connection",
            "close"
        )

        self.end_headers()

        try:

            self.wfile.write(data)
            self.wfile.flush()

        except Exception:
            pass


    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    def do_GET(self):

        # Health
        if self.path in (
            "/",
            "/health",
            "/v1/health"
        ):

            self.send_json(
                200,
                {
                    "ok": True,

                    "model": MODEL,

                    "keys": len(KEYS),

                    "limits": {
                        "rpm": SAFE_RPM,
                        "tpm": SAFE_TPM,
                        "rpd": SAFE_RPD,
                        "tpd": SAFE_TPD
                    },

                    "key_status": [
                        key.info()
                        for key in KEYS
                    ]
                }
            )

            return


        # OpenAI-compatible model list
        if self.path == "/v1/models":

            self.send_json(
                200,
                {
                    "object": "list",

                    "data": [
                        {
                            "id": MODEL,
                            "object": "model",
                            "owned_by": "groq"
                        }
                    ]
                }
            )

            return


        self.send_json(
            404,
            {
                "error": {
                    "message":
                        "Not found"
                }
            }
        )


    # --------------------------------------------------------
    # POST
    # --------------------------------------------------------

    def do_POST(self):

        if self.path != (
            "/v1/chat/completions"
        ):

            self.send_json(
                404,
                {
                    "error": {
                        "message":
                            "Unsupported endpoint"
                    }
                }
            )

            return


        try:

            length = int(
                self.headers.get(
                    "Content-Length",
                    "0"
                )
            )

        except Exception:

            length = 0


        if length <= 0:

            self.send_json(
                400,
                {
                    "error": {
                        "message":
                            "Empty body"
                    }
                }
            )

            return


        body = self.rfile.read(
            length
        )

        # Normalizacja
        body = normalize(body)

        # Szacowanie tokenów
        estimated_tokens = (
            estimate_tokens(body)
        )

        print(
            "[queue]",
            "estimated_tokens=",
            estimated_tokens
        )


        # Pobranie klucza
        try:

            key = wait_for_key(
                estimated_tokens
            )

        except TimeoutError as error:

            self.send_json(
                429,
                {
                    "error": {
                        "type":
                            "proxy_rate_limit",

                        "message":
                            str(error)
                    }
                }
            )

            return


        print(
            f"[key {key.number}] "
            "request started"
        )


        # ----------------------------------------------------
        # REQUEST / RETRY
        # ----------------------------------------------------

        for attempt in range(
            MAX_RETRIES + 1
        ):

            status, headers, response = (
                groq_request(
                    self.path,
                    body,
                    key,
                    self.headers
                )
            )


            # Sukces / inny status
            if status != 429:

                self.write_response(
                    status,
                    headers,
                    response
                )

                print(
                    f"[key {key.number}] "
                    f"status={status}"
                )

                return


            # ------------------------------------------------
            # 429
            # ------------------------------------------------

            wait = retry_after(
                headers
            )

            if wait is None:

                wait = min(
                    60,
                    2 ** attempt
                )


            key.cooldown(
                wait
            )


            print(
                f"[key {key.number}] "
                f"429 -> cooldown "
                f"{wait:.2f}s"
            )


            # Spróbuj innego klucza
            other_key = select_key(
                estimated_tokens
            )


            if other_key:

                other_key.reserve(
                    estimated_tokens
                )

                key = other_key

                print(
                    f"[key {key.number}] "
                    "switching key"
                )

                continue


            # Brak wolnego klucza
            time.sleep(wait)


        # Wszystkie retry zakończone
        self.write_response(
            status,
            headers,
            response
        )


    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    def write_response(
        self,
        status,
        headers,
        body
    ):

        self.send_response(
            status
        )


        content_type = (
            headers.get(
                "Content-Type"
            )
            or headers.get(
                "content-type"
            )
            or "application/json"
        )


        self.send_header(
            "Content-Type",
            content_type
        )


        # Przekazujemy informacje o limitach
        # z Groq do klienta.

        rate_headers = (
            "retry-after",

            "x-ratelimit-limit-requests",

            "x-ratelimit-limit-tokens",

            "x-ratelimit-remaining-requests",

            "x-ratelimit-remaining-tokens",

            "x-ratelimit-reset-requests",

            "x-ratelimit-reset-tokens",
        )


        for name in rate_headers:

            value = (
                headers.get(name)
                or headers.get(
                    name.title()
                )
            )

            if value:

                self.send_header(
                    name,
                    value
                )


        self.send_header(
            "Content-Length",
            str(len(body))
        )


        self.send_header(
            "Connection",
            "close"
        )


        self.end_headers()


        try:

            self.wfile.write(
                body
            )

            self.wfile.flush()

        except Exception:
            pass


# ============================================================
# MAIN
# ============================================================

def main():

    if not KEYS:

        print()
        print(
            "ERROR: Brak kluczy Groq."
        )

        print()
        print(
            "Plik api.txt powinien wyglądać tak:"
        )

        print()
        print(
            "apikey=TWÓJ_KLUCZ_1"
        )

        print(
            "apikey=TWÓJ_KLUCZ_2"
        )

        print(
            "apikey=TWÓJ_KLUCZ_3"
        )

        print()

        raise SystemExit(1)


    print()
    print(
        "=========================================="
    )

    print(
        " OpenCode -> Groq Multi-Key Proxy"
    )

    print(
        "=========================================="
    )

    print(
        f"Endpoint: http://{HOST}:{PORT}/v1"
    )

    print(
        f"Model:    {MODEL}"
    )

    print(
        f"Keys:     {len(KEYS)}"
    )

    print(
        f"Local RPM: {SAFE_RPM}"
    )

    print(
        f"Local TPM: {SAFE_TPM}"
    )

    print(
        f"Local RPD: {SAFE_RPD}"
    )

    print(
        f"Local TPD: {SAFE_TPD}"
    )

    print()


    # Nie wypisujemy kluczy API.

    for key in KEYS:

        print(
            f"Key {key.number}: configured"
        )


    print()

    print(
        "Health: "
        f"http://{HOST}:{PORT}/health"
    )

    print()

    print(
        "Starting proxy..."
    )

    print()


    server = ThreadingHTTPServer(
        (HOST, PORT),
        Handler
    )


    try:

        server.serve_forever()

    except KeyboardInterrupt:

        print()
        print(
            "Stopping..."
        )

    finally:

        server.server_close()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
