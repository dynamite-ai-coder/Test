#!/usr/bin/env python3
"""
OpenCode -> Groq Free Rate-Limit Proxy
Single-file, dependency-free Python proxy.

Default:
    Local proxy: http://127.0.0.1:8787/v1
    Groq:        https://api.groq.com/openai/v1
    Model:       openai/gpt-oss-20b

Designed for Groq Free:
    RPM = 30
    RPD = 1000
    TPM = 8000
    TPD = 200000

The proxy does NOT bypass Groq limits.
It queues/throttles requests so OpenCode does not unnecessarily
hit Groq's rate limits.

API key:
    export GROQ_API_KEY="your-key"

Optional:
    export GROQ_MODEL="openai/gpt-oss-20b"
    export PROXY_PORT="8787"
    export SAFE_TPM="7000"
    export SAFE_RPM="25"
    export SAFE_RPD="950"
    export SAFE_TPD="190000"
"""

import os
import sys
import json
import time
import socket
import signal
import threading
import urllib.request
import urllib.error
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


# ============================================================
# CONFIG
# ============================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

GROQ_BASE_URL = os.environ.get(
    "GROQ_BASE_URL",
    "https://api.groq.com/openai/v1"
).rstrip("/")

DEFAULT_MODEL = os.environ.get(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)

HOST = os.environ.get(
    "PROXY_HOST",
    "127.0.0.1"
)

PORT = int(os.environ.get(
    "PROXY_PORT",
    "8787"
))

# Safety margins below Groq Free limits.
SAFE_RPM = int(os.environ.get("SAFE_RPM", "25"))
SAFE_RPD = int(os.environ.get("SAFE_RPD", "950"))
SAFE_TPM = int(os.environ.get("SAFE_TPM", "7000"))
SAFE_TPD = int(os.environ.get("SAFE_TPD", "190000"))

# Maximum completion requested by OpenCode.
# This prevents accidentally huge completions.
DEFAULT_MAX_COMPLETION_TOKENS = int(
    os.environ.get("DEFAULT_MAX_COMPLETION_TOKENS", "4096")
)

MAX_COMPLETION_TOKENS = int(
    os.environ.get("MAX_COMPLETION_TOKENS", "8192")
)

# Approximation used before sending a request.
# We intentionally reserve some margin.
CHARS_PER_TOKEN = 4.0

# Never wait forever.
MAX_QUEUE_WAIT = int(
    os.environ.get("MAX_QUEUE_WAIT", "900")
)

# Number of automatic retries after a 429.
MAX_RETRIES = int(
    os.environ.get("MAX_RETRIES", "5")
)

# Initial retry delay if Groq doesn't provide Retry-After.
INITIAL_BACKOFF = float(
    os.environ.get("INITIAL_BACKOFF", "2")
)

MAX_BACKOFF = float(
    os.environ.get("MAX_BACKOFF", "60")
)


# ============================================================
# STATE
# ============================================================

state_lock = threading.Lock()

request_times = deque()
token_events = deque()

daily_requests = 0
daily_tokens = 0

day_started = time.time()

total_requests = 0
total_tokens = 0
total_429 = 0

shutdown_event = threading.Event()


# ============================================================
# UTILS
# ============================================================

def now():
    return time.time()


def cleanup_windows():
    """
    Remove old entries from rolling RPM/TPM windows.
    """
    current = now()

    with state_lock:
        while request_times and current - request_times[0] >= 60:
            request_times.popleft()

        while token_events and current - token_events[0][0] >= 60:
            token_events.popleft()


def reset_daily_if_needed():
    global daily_requests
    global daily_tokens
    global day_started

    current = now()

    with state_lock:
        if current - day_started >= 86400:
            daily_requests = 0
            daily_tokens = 0
            day_started = current


def estimate_tokens_from_body(body):
    """
    Conservative token estimate.

    We don't require tiktoken, so this is intentionally simple.
    """
    try:
        data = json.loads(body.decode("utf-8"))
    except Exception:
        return max(1, len(body) // 4)

    try:
        compact = json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":")
        )

        estimated_input = max(
            1,
            int(len(compact) / CHARS_PER_TOKEN)
        )

        requested_output = int(
            data.get(
                "max_completion_tokens",
                data.get(
                    "max_tokens",
                    DEFAULT_MAX_COMPLETION_TOKENS
                )
            ) or DEFAULT_MAX_COMPLETION_TOKENS
        )

        requested_output = min(
            requested_output,
            MAX_COMPLETION_TOKENS
        )

        return estimated_input + requested_output

    except Exception:
        return max(1, len(body) // 4)


def get_model_from_body(body):
    try:
        data = json.loads(body.decode("utf-8"))
        return data.get("model") or DEFAULT_MODEL
    except Exception:
        return DEFAULT_MODEL


def parse_retry_after(headers):
    value = headers.get("Retry-After")

    if not value:
        value = headers.get("retry-after")

    if not value:
        return None

    try:
        return max(0.1, float(value))
    except Exception:
        return None


def safe_header(headers, name):
    value = headers.get(name)

    if value is None:
        value = headers.get(name.lower())

    return value


def local_ip():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("1.1.1.1", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ============================================================
# RATE LIMITER
# ============================================================

def current_usage():
    cleanup_windows()
    reset_daily_if_needed()

    with state_lock:
        rolling_tokens = sum(
            amount for _, amount in token_events
        )

        return {
            "rpm": len(request_times),
            "tpm": rolling_tokens,
            "rpd": daily_requests,
            "tpd": daily_tokens,
        }


def calculate_wait(estimated_tokens):
    """
    Return number of seconds to wait before a request is safe.
    """
    cleanup_windows()
    reset_daily_if_needed()

    current = now()

    with state_lock:
        # Daily request limit
        if daily_requests >= SAFE_RPD:
            return max(
                1,
                86400 - (current - day_started)
            )

        # Daily token limit
        if daily_tokens + estimated_tokens >= SAFE_TPD:
            return max(
                1,
                86400 - (current - day_started)
            )

        # RPM
        if len(request_times) >= SAFE_RPM:
            oldest = request_times[0]
            return max(
                0.1,
                60 - (current - oldest)
            )

        # TPM
        rolling_tokens = sum(
            amount for _, amount in token_events
        )

        if rolling_tokens + estimated_tokens >= SAFE_TPM:
            oldest_time = token_events[0][0]

            return max(
                0.1,
                60 - (current - oldest_time)
            )

    return 0


def wait_for_capacity(estimated_tokens):
    """
    Wait until this request fits our local safety budget.
    """
    started = now()

    while not shutdown_event.is_set():

        waited = now() - started

        if waited > MAX_QUEUE_WAIT:
            raise TimeoutError(
                "Request stayed in queue too long."
            )

        wait_time = calculate_wait(estimated_tokens)

        if wait_time <= 0:
            current = now()

            with state_lock:
                request_times.append(current)
                token_events.append(
                    (current, estimated_tokens)
                )

            return

        # Small jitter prevents synchronized requests.
        time.sleep(
            min(wait_time + 0.05, 5)
        )

    raise RuntimeError("Proxy shutting down")


def register_daily_usage(actual_tokens):
    global daily_requests
    global daily_tokens
    global total_requests
    global total_tokens

    reset_daily_if_needed()

    with state_lock:
        daily_requests += 1
        daily_tokens += actual_tokens

        total_requests += 1
        total_tokens += actual_tokens


# ============================================================
# REQUEST BODY NORMALIZATION
# ============================================================

def normalize_request(body):
    """
    Adjust OpenCode's request to be safer for Groq Free.

    We don't rewrite messages or system prompts.
    Only conservative generation settings are adjusted.
    """
    try:
        data = json.loads(body.decode("utf-8"))
    except Exception:
        return body

    if not isinstance(data, dict):
        return body

    # Model
    if not data.get("model"):
        data["model"] = DEFAULT_MODEL

    # Prevent accidentally enormous completions.
    key = None

    if "max_completion_tokens" in data:
        key = "max_completion_tokens"
    elif "max_tokens" in data:
        key = "max_tokens"

    if key:
        try:
            requested = int(data[key])

            if requested <= 0:
                data[key] = DEFAULT_MAX_COMPLETION_TOKENS
            else:
                data[key] = min(
                    requested,
                    MAX_COMPLETION_TOKENS
                )
        except Exception:
            data[key] = DEFAULT_MAX_COMPLETION_TOKENS
    else:
        data["max_completion_tokens"] = (
            DEFAULT_MAX_COMPLETION_TOKENS
        )

    return json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":")
    ).encode("utf-8")


# ============================================================
# GROQ HTTP
# ============================================================

def forward_request(path, body, incoming_headers):
    """
    Forward request to Groq.

    Returns:
        status, headers, response_body
    """
    url = GROQ_BASE_URL + path

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": incoming_headers.get(
            "Content-Type",
            "application/json"
        ),
        "Accept": incoming_headers.get(
            "Accept",
            "application/json"
        ),
        "User-Agent": "opencode-groq-proxy/1.0",
    }

    # Forward selected harmless headers.
    for name in (
        "X-Stainless-Lang",
        "X-Stainless-Package-Version",
        "OpenAI-Beta",
    ):
        if name in incoming_headers:
            headers[name] = incoming_headers[name]

    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=600
        ) as response:

            response_body = response.read()

            response_headers = {
                k: v
                for k, v in response.headers.items()
            }

            return (
                response.status,
                response_headers,
                response_body
            )

    except urllib.error.HTTPError as error:

        response_body = error.read()

        response_headers = {
            k: v
            for k, v in error.headers.items()
        }

        return (
            error.code,
            response_headers,
            response_body
        )

    except urllib.error.URLError as error:

        payload = {
            "error": {
                "message": f"Connection to Groq failed: {error}",
                "type": "proxy_connection_error"
            }
        }

        return (
            502,
            {},
            json.dumps(payload).encode("utf-8")
        )

    except Exception as error:

        payload = {
            "error": {
                "message": f"Proxy error: {error}",
                "type": "proxy_error"
            }
        }

        return (
            502,
            {},
            json.dumps(payload).encode("utf-8")
        )


# ============================================================
# HTTP HANDLER
# ============================================================

class ProxyHandler(BaseHTTPRequestHandler):

    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # Compact logging.
        sys.stdout.write(
            "[proxy] " + (fmt % args) + "\n"
        )
        sys.stdout.flush()

    def send_json(self, status, payload):

        data = json.dumps(
            payload,
            ensure_ascii=False
        ).encode("utf-8")

        self.send_response(status)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
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
        except Exception:
            pass

    def do_GET(self):

        path = urlsplit(self.path).path

        if path in ("/", "/health", "/v1/health"):

            usage = current_usage()

            self.send_json(
                200,
                {
                    "ok": True,
                    "service": "opencode-groq-proxy",
                    "model": DEFAULT_MODEL,
                    "groq": GROQ_BASE_URL,
                    "limits": {
                        "safe_rpm": SAFE_RPM,
                        "safe_rpd": SAFE_RPD,
                        "safe_tpm": SAFE_TPM,
                        "safe_tpd": SAFE_TPD
                    },
                    "usage": usage
                }
            )

            return

        # OpenAI-compatible model listing.
        if path == "/v1/models":

            model = {
                "id": DEFAULT_MODEL,
                "object": "model",
                "owned_by": "groq"
            }

            self.send_json(
                200,
                {
                    "object": "list",
                    "data": [model]
                }
            )

            return

        self.send_json(
            404,
            {
                "error": {
                    "message": "Not found"
                }
            }
        )

    def do_POST(self):

        path = urlsplit(self.path).path

        content_length = self.headers.get(
            "Content-Length"
        )

        try:
            length = int(
                content_length or "0"
            )
        except Exception:
            length = 0

        if length <= 0:
            self.send_json(
                400,
                {
                    "error": {
                        "message": "Empty request body"
                    }
                }
            )
            return

        if length > 25 * 1024 * 1024:
            self.send_json(
                413,
                {
                    "error": {
                        "message": "Request body too large"
                    }
                }
            )
            return

        try:
            original_body = self.rfile.read(length)
        except Exception as error:
            self.send_json(
                400,
                {
                    "error": {
                        "message": str(error)
                    }
                }
            )
            return

        # Only actively rate-limit Chat Completions.
        if path != "/v1/chat/completions":

            status, headers, response_body = forward_request(
                path,
                original_body,
                self.headers
            )

            self.write_upstream_response(
                status,
                headers,
                response_body
            )

            return

        body = normalize_request(
            original_body
        )

        estimated_tokens = estimate_tokens_from_body(
            body
        )

        model = get_model_from_body(body)

        print(
            f"[queue] model={model} "
            f"estimated_tokens={estimated_tokens}"
        )

        # Queue until our local Free-plan budget allows it.
        try:
            wait_for_capacity(
                estimated_tokens
            )
        except TimeoutError as error:
            self.send_json(
                429,
                {
                    "error": {
                        "message": str(error),
                        "type": "proxy_queue_timeout"
                    }
                }
            )
            return

        # Forward with automatic 429 retry.
        response = None

        for attempt in range(
            MAX_RETRIES + 1
        ):

            status, headers, response_body = (
                forward_request(
                    path,
                    body,
                    self.headers
                )
            )

            response = (
                status,
                headers,
                response_body
            )

            if status != 429:
                break

            global total_429

            with state_lock:
                total_429 += 1

            retry_after = parse_retry_after(
                headers
            )

            if retry_after is None:

                retry_after = min(
                    MAX_BACKOFF,
                    INITIAL_BACKOFF * (
                        2 ** attempt
                    )
                )

            print(
                f"[429] Groq rate limit. "
                f"waiting {retry_after:.2f}s "
                f"(attempt {attempt + 1}/"
                f"{MAX_RETRIES + 1})"
            )

            time.sleep(
                retry_after
            )

        status, headers, response_body = response

        # Register estimated request usage.
        register_daily_usage(
            estimated_tokens
        )

        self.write_upstream_response(
            status,
            headers,
            response_body
        )

        print(
            f"[response] status={status} "
            f"model={model} "
            f"estimated_tokens={estimated_tokens}"
        )

    def write_upstream_response(
        self,
        status,
        headers,
        body
    ):

        self.send_response(status)

        # Preserve useful Groq headers.
        allowed_headers = {
            "content-type",
            "cache-control",
            "retry-after",
            "x-ratelimit-limit-requests",
            "x-ratelimit-limit-tokens",
            "x-ratelimit-remaining-requests",
            "x-ratelimit-remaining-tokens",
            "x-ratelimit-reset-requests",
            "x-ratelimit-reset-tokens",
        }

        sent_length = False

        for key, value in headers.items():

            if key.lower() in allowed_headers:

                # Don't duplicate Content-Length.
                if key.lower() == "content-length":
                    continue

                self.send_header(
                    key,
                    value
                )

            if key.lower() == "content-type":
                pass

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
            self.wfile.write(body)
            self.wfile.flush()
        except Exception:
            pass


# ============================================================
# SERVER
# ============================================================

class ProxyServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def shutdown_handler(signum, frame):

    print(
        "\n[proxy] Shutting down..."
    )

    shutdown_event.set()


def print_startup():

    print()
    print("=" * 62)
    print(" OpenCode -> Groq Free Rate-Limit Proxy")
    print("=" * 62)
    print()
    print(f" Local URL:     http://{HOST}:{PORT}")
    print(
        f" OpenAI base:   http://{HOST}:{PORT}/v1"
    )
    print(
        f" Groq endpoint: {GROQ_BASE_URL}"
    )
    print(
        f" Model:         {DEFAULT_MODEL}"
    )
    print()
    print(" Safe limits:")
    print(f"   RPM: {SAFE_RPM}")
    print(f"   RPD: {SAFE_RPD}")
    print(f"   TPM: {SAFE_TPM}")
    print(f"   TPD: {SAFE_TPD}")
    print()
    print(
        " Health: "
        f"http://{HOST}:{PORT}/health"
    )
    print()
    print(
        " API key: "
        + ("configured" if GROQ_API_KEY else "MISSING")
    )
    print()
    print("=" * 62)
    print()


def main():

    if not GROQ_API_KEY:

        print(
            "[ERROR] GROQ_API_KEY is not set."
        )

        print()
        print(
            "Termux:"
        )
        print(
            '  export GROQ_API_KEY="YOUR_GROQ_KEY"'
        )
        print()
        print(
            "Then:"
        )
        print(
            "  python groq_proxy.py"
        )

        sys.exit(1)

    signal.signal(
        signal.SIGINT,
        shutdown_handler
    )

    signal.signal(
        signal.SIGTERM,
        shutdown_handler
    )

    print_startup()

    server = ProxyServer(
        (HOST, PORT),
        ProxyHandler
    )

    try:
        server.serve_forever(
            poll_interval=0.5
        )

    except KeyboardInterrupt:
        pass

    finally:

        shutdown_event.set()

        server.server_close()

        print(
            "[proxy] stopped."
        )


if __name__ == "__main__":
    main()
