import logging
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from typing import Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manage Selenium browser sessions."""
    
    def __init__(self, headless: bool = True, binary_path: Optional[str] = None):
        self.headless = headless
        self.binary_path = binary_path
        self.driver: Optional[webdriver.Chrome] = None
    
    def start_browser(self) -> webdriver.Chrome:
        """Initialize and start Chrome browser."""
        try:
            options = webdriver.ChromeOptions()
            
            if self.headless:
                options.add_argument("--headless")
            
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1280,720")
            options.add_argument("--start-maximized")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            if self.binary_path and os.path.exists(self.binary_path):
                options.binary_location = self.binary_path
            
            # Use webdriver-manager to automatically handle ChromeDriver
            service = Service(ChromeDriverManager().install())
            
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(30)
            self.driver.set_script_timeout(30)
            
            logger.info("Browser started successfully")
            return self.driver
            
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            raise
    
    def stop_browser(self) -> None:
        """Stop and clean up browser session."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Browser stopped")
            except Exception as e:
                logger.error(f"Error stopping browser: {e}")
            finally:
                self.driver = None
    
    def navigate_to(self, url: str, timeout: int = 30) -> bool:
        """Navigate to URL and wait for page load."""
        if not self.driver:
            logger.error("Browser not initialized")
            return False
        
        try:
            self.driver.get(url)
            # Wait for body to be present
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            logger.info(f"Navigated to {url}")
            return True
            
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return False
    
    def find_element_by_selector(self, selector: str, by: By = By.CSS_SELECTOR, timeout: int = 10):
        """Find element by selector with explicit wait."""
        if not self.driver:
            return None
        
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
            return element
        except Exception as e:
            logger.warning(f"Element not found with selector '{selector}': {e}")
            return None
    
    def click_element(self, element) -> bool:
        """Click element with wait for clickability."""
        if not self.driver or not element:
            return False
        
        try:
            WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(element))
            element.click()
            logger.info(f"Clicked element")
            return True
        except Exception as e:
            logger.error(f"Failed to click element: {e}")
            return False
    
    def type_text(self, element, text: str) -> bool:
        """Type text into element."""
        if not element:
            return False
        
        try:
            element.clear()
            element.send_keys(text)
            logger.info(f"Typed text into element")
            return True
        except Exception as e:
            logger.error(f"Failed to type text: {e}")
            return False
    
    def wait_for_element(self, selector: str, by: By = By.CSS_SELECTOR, timeout: int = 10) -> bool:
        """Wait for element to be present."""
        if not self.driver:
            return False
        
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
            logger.info(f"Element appeared: {selector}")
            return True
        except Exception as e:
            logger.debug(f"Wait for element timed out: {e}")
            return False
    
    def take_screenshot(self, filepath: str) -> bool:
        """Take screenshot and save to file."""
        if not self.driver:
            return False
        
        try:
            os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
            self.driver.save_screenshot(filepath)
            logger.info(f"Screenshot saved to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return False
    
    def get_page_source(self) -> str:
        """Get current page HTML."""
        if not self.driver:
            return ""
        
        try:
            return self.driver.page_source
        except Exception as e:
            logger.error(f"Failed to get page source: {e}")
            return ""
    
    def get_page_title(self) -> str:
        """Get current page title."""
        if not self.driver:
            return ""
        
        try:
            return self.driver.title
        except Exception as e:
            logger.error(f"Failed to get page title: {e}")
            return ""
    
    def get_current_url(self) -> str:
        """Get current URL."""
        if not self.driver:
            return ""
        
        try:
            return self.driver.current_url
        except Exception as e:
            logger.error(f"Failed to get current URL: {e}")
            return ""
