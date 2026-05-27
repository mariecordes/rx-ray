# TODO: IMPORT FROM SRC
import os
import sys
import logging
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.knowledge_graph.rxnorm_connector import RxNormConnector
from src.knowledge_graph.openfda_connector import OpenFDAConnector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run setup and connectivity tests."""
    
    # Allow optional drug name argument for testing in CLI
    drug_name = sys.argv[1] if len(sys.argv) > 1 else "aspirin"
    
    logger.info("=" * 60)
    logger.info("rx-ray Data Integration Setup & Test")
    logger.info("=" * 60)
    
    # Test OpenFDA API (no credentials needed)
    logger.info("\n[1/3] Testing OpenFDA API...")
    openfda = OpenFDAConnector()
    openfda_result = openfda.test_api(drug_name)
    
    # Test RxNorm MySQL connection (requires setup)
    logger.info("\n[2/3] Testing RxNorm MySQL connection...")
    
    logger.info(f"Attempting connection to {os.getenv('RXNORM_HOST', 'localhost')}...")
    rxnorm = RxNormConnector()
    rxnorm_connected = rxnorm.connect()
    
    if rxnorm_connected:
        rxnorm_result = rxnorm.test_query(drug_name)
        logger.info(f"RxNorm query result for '{drug_name}': {rxnorm_result}")
    #     if rxnorm_result and openfda_result:
    #         # Test linking by RXCUI
    #         rxcui = rxnorm_result.get("RXCUI")
    #         logger.info(f"\n[3/3] Testing cross-source linking (RXCUI: {rxcui})...")
    #         openfda.test_rxcui_search(str(rxcui))
        rxnorm.close()
    else:
        logger.warning("Skipping RxNorm tests (connection failed)")
        logger.info("  To set up: configure environment variables:")
        logger.info("    export RXNORM_HOST=localhost")
        logger.info("    export RXNORM_USER=your_user")
        logger.info("    export RXNORM_PASSWORD=your_password")
        logger.info("    export RXNORM_DATABASE=RxNorm")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Setup Test Summary:")
    logger.info(f"  OpenFDA API: {'OK' if openfda_result else 'FAILED'}")
    logger.info(f"  RxNorm MySQL: {'OK' if rxnorm_connected else 'NOT CONFIGURED'}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
