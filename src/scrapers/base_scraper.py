"""
Base Scraper with Playwright

Abstract base class for all scrapers. Implements the layered pipeline architecture
from research: scrape (crawl) -> parse (transform) -> store.

Features:
- Playwright with headless browser automation
- playwright-stealth for anti-detection (not hand-rolled)
- Token bucket rate limiting (respects site rate limits)
- tenacity retry logic with exponential backoff (not manual try/catch)
- Async context manager pattern for proper resource cleanup

Subclasses must implement parse() method for site-specific extraction logic.
"""

from abc import ABC, abstractmethod
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from tenacity import retry, wait_exponential, stop_after_attempt
from src.utils.rate_limiter import TokenBucketRateLimiter
from src.utils.stealth import setup_stealth_page, get_browser_launch_args


class BaseScraper(ABC):
    """
    Abstract base class for web scrapers using Playwright.

    This class handles all the common scraping infrastructure:
    - Browser launch and stealth configuration
    - Rate limiting (respects 2-5 second delays)
    - Retry logic with exponential backoff
    - Proper resource cleanup

    Subclasses only need to implement parse() for site-specific data extraction.

    Args:
        url (str): The URL to scrape
        rate_limiter (TokenBucketRateLimiter): Rate limiter instance for request throttling

    Example:
        class GreyhoundStatsScraper(BaseScraper):
            async def parse(self, html: str) -> dict:
                # Site-specific parsing logic
                soup = BeautifulSoup(html, 'html.parser')
                return {'races': [...]}

        rate_limiter = TokenBucketRateLimiter(rate=0.5)  # 2-sec delays
        scraper = GreyhoundStatsScraper('https://example.com', rate_limiter)
        data = await scraper.run()
    """

    def __init__(self, url: str, rate_limiter: TokenBucketRateLimiter):
        self.url = url
        self.rate_limiter = rate_limiter

    @retry(
        wait=wait_exponential(min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True
    )
    async def scrape(self) -> str:
        """
        Scrape the URL and return raw HTML content.

        Uses Playwright with:
        - Headless browser
        - Stealth configuration (anti-detection)
        - Rate limiting (waits before navigation)
        - Network idle wait (ensures JS finishes loading)

        Retries up to 3 times with exponential backoff (2-10 seconds) on failure.

        Returns:
            str: Raw HTML content of the page

        Raises:
            Exception: If scraping fails after all retry attempts
        """
        async with async_playwright() as p:
            # Launch browser with stealth args
            browser: Browser = await p.chromium.launch(
                headless=True,
                args=get_browser_launch_args()
            )

            try:
                # Create context with realistic viewport and user agent
                context: BrowserContext = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )

                # Create page and apply stealth patches
                page: Page = await context.new_page()
                page = await setup_stealth_page(page)

                # CRITICAL: Rate limit BEFORE navigation (respects site rate limits)
                await self.rate_limiter.acquire()

                # Navigate and wait for network to be idle (JS finishes loading)
                await page.goto(self.url, wait_until='networkidle', timeout=30000)

                # Extract HTML content
                html = await page.content()

                return html

            finally:
                # Always clean up browser resources
                await browser.close()

    @abstractmethod
    async def parse(self, html: str) -> dict:
        """
        Parse raw HTML into structured data.

        Subclasses must implement this method for site-specific extraction.

        Args:
            html (str): Raw HTML content from scrape()

        Returns:
            dict: Structured data extracted from the page
        """
        pass

    async def run(self) -> dict:
        """
        Execute the full scraping pipeline: scrape -> parse.

        Returns:
            dict: Parsed data from the page

        Raises:
            Exception: If scraping or parsing fails
        """
        html = await self.scrape()
        data = await self.parse(html)
        return data
