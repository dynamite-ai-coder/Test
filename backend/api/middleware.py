import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from datetime import datetime

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware:
    """Middleware for global error handling."""
    
    def __init__(self, app: FastAPI):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        try:
            await self.app(scope, receive, send)
        except Exception as e:
            logger.error(f"Unhandled error: {e}", exc_info=True)
            
            response = JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            await response(scope, receive, send)


class SecurityHeadersMiddleware:
    """Add security headers to all responses."""
    
    def __init__(self, app: FastAPI):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                
                # Add security headers
                headers.extend([
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"x-xss-protection", b"1; mode=block"),
                    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
                ])
                
                message["headers"] = headers
            
            await send(message)
        
        await self.app(scope, receive, send_wrapper)
