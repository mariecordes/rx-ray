import logging
import json
import requests
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_URL = "https://api.fda.gov/drug/label.json"


class OpenFDAConnector:
    """Connector for fetching drug label data from OpenFDA."""
    
    def __init__(self):
        pass
        
    def query_api_for_generic_name(self, drug_name: str, search_limit: int = None) -> dict:
        """Query OpenFDA API for a drug by generic name."""
        
        params = {
            "search": f"openfda.generic_name:{drug_name}",
        }
        
        if search_limit is not None:
            params["limit"] = search_limit
        
        try:
            logger.info(f"Querying OpenFDA API for '{drug_name}'...")
            response = requests.get(BASE_URL, params=params, timeout=10)
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
