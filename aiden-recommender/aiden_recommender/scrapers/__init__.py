from .france_travail.scraper import FranceTravailScraper
from .indeed.scraper import IndeedScraper
from .wtj.scraper import WelcomeToTheJungleScraper

france_travail_scraper = FranceTravailScraper(results_multiplier=2)
indeed_scraper = IndeedScraper()
wtj_scraper = WelcomeToTheJungleScraper(results_multiplier=2)
