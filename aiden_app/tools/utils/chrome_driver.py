from selenium import webdriver
from selenium.webdriver.chrome.options import Options


class ChromeDriver:
    def setup_chrome_options(self) -> Options:
        options = Options()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--headless')

        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        options.add_argument(f'user-agent={user_agent}')

        options.add_argument('--start-maximized')
        options.add_experimental_option(
            'prefs',
            {
                'profile.default_content_setting_values.cookies': 2,
                'profile.default_content_setting_values.notifications': 2,
                'profile.default_content_setting_values.popups': 2,
                'profile.default_content_setting_values.geolocation': 2,
                'profile.default_content_setting_values.automatic_downloads': 1,
                'download.default_directory': r'C:\temp',
                'download.prompt_for_download': False,
                'download.directory_upgrade': True,
                'safebrowsing.enabled': False,
            },
        )
        return options

    def __init__(self):
        self.options = self.setup_chrome_options()
        self.driver = None

    def start(self):
        if self.driver is None or not self.driver.session_id:
            self.driver = webdriver.Chrome(options=self.options)
        try:
            self.driver.current_url
        except Exception:
            self.driver = webdriver.Chrome(options=self.options)
        return self.driver

    def quit(self):
        if self.driver:
            self.driver.quit()
