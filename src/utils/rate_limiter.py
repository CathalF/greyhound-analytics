"""
Token Bucket Rate Limiter

Implements the industry-standard token bucket algorithm for rate limiting.
Not hand-rolled - this is the recommended pattern from research (01-RESEARCH.md).

Token bucket pattern:
- Tokens are added to the bucket at a fixed rate
- Each request consumes 1 token
- If no tokens available, request waits until one is refilled
- Allows bursts up to capacity while maintaining average rate
"""

import time
import asyncio


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for respectful web scraping.

    Args:
        rate (float): Tokens added per second. Default 0.5 = 2-second delays between requests
        capacity (int): Maximum tokens in bucket. Allows bursts up to this size

    Example:
        rate_limiter = TokenBucketRateLimiter(rate=0.5, capacity=5)
        await rate_limiter.acquire()  # Wait if necessary, then consume 1 token
    """

    def __init__(self, rate: float = 0.5, capacity: int = 5):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()

    async def acquire(self):
        """
        Acquire a token, waiting if necessary.

        Calculates elapsed time since last update, adds tokens at the configured rate
        (up to capacity), then waits if insufficient tokens are available. Once a token
        is available, consumes it and returns.

        This is async-compatible for use with Playwright and other async scraping code.
        """
        while True:
            now = time.time()
            elapsed = now - self.last_update

            # Add tokens based on elapsed time, capped at capacity
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            # If we have at least 1 token, consume it and return
            if self.tokens >= 1:
                self.tokens -= 1
                return

            # Otherwise, wait a bit and try again
            await asyncio.sleep(0.1)
