"""
Playwright Stealth Configuration

Applies anti-detection patches to Playwright pages using playwright-stealth library.
Not custom fingerprinting - uses battle-tested library (research warning: "Modern
anti-bot systems analyze dozens of signals").

This helper configures:
- playwright-stealth patches (fixes detection vectors)
- Realistic viewport and user agent
- Browser launch args to disable automation signals
"""

from playwright.async_api import Page, Browser
from playwright_stealth import Stealth


async def setup_stealth_page(page: Page) -> Page:
    """
    Apply stealth configuration to a Playwright page.

    Uses playwright-stealth library to patch common bot detection vectors including:
    - navigator.webdriver property
    - Chrome runtime detection
    - Permissions API
    - Plugins and MIME types
    - WebGL vendor/renderer
    - And many more fingerprinting techniques

    Also sets realistic viewport, user agent, and headers.

    Args:
        page: Playwright Page object to configure

    Returns:
        The same Page object, now configured with stealth patches

    Example:
        browser = await playwright.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        page = await browser.new_page()
        page = await setup_stealth_page(page)
        await page.goto(url)
    """
    # Apply playwright-stealth patches
    stealth = Stealth()
    await stealth.apply_stealth_async(page)

    # Set realistic viewport
    await page.set_viewport_size({"width": 1920, "height": 1080})

    # Set realistic user agent (Windows 10, Chrome 120)
    await page.set_extra_http_headers({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })

    return page


def get_browser_launch_args() -> list[str]:
    """
    Get recommended browser launch arguments for stealth.

    Returns:
        List of command-line arguments to pass to browser.launch()

    Example:
        browser = await playwright.chromium.launch(
            headless=True,
            args=get_browser_launch_args()
        )
    """
    return [
        '--disable-blink-features=AutomationControlled',
    ]
