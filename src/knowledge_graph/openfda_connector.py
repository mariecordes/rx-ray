import os
import logging
import json
import requests
from pathlib import Path
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
from dotenv import load_dotenv  # type: ignore
load_dotenv()


class OpenFDAConnector:
    """Connector for fetching drug label data from OpenFDA."""
    
    def __init__(self, base_url: str = None, timeout: int = 10):
        self.base_url = os.getenv("OPENFDA_BASE_URL", base_url)
        print(f"Using OpenFDA Base URL: {self.base_url}")
        self.timeout = timeout
    
    def query_api_for_generic_name(self, drug_name: str, search_limit: int = None) -> dict:
        """Query OpenFDA API for a drug by generic name."""
        
        params = {
            "search": f"openfda.generic_name:{drug_name}",
        }
        
        if search_limit is not None:
            params["limit"] = search_limit
        
        try:
            logger.info(f"Querying OpenFDA API for '{drug_name}'...")
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            total = data.get("meta", {}).get("results", {}).get("total", 0)
            
            if total > 0:
                logger.info(f"Found {total} result(s) for '{drug_name}'")
                return data["results"]
            else:
                logger.warning(f"No results found for '{drug_name}'")
                return {}
        
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenFDA API request failed: {e}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenFDA response: {e}")
            return {}


if __name__ == "__main__":
    pass
