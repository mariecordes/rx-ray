"""
Extract and transform OpenFDA data for top 300 drugs.

Pipeline:
1. Load top 300 drugs from ClinCalc
2. Query OpenFDA API for each drug
3. Save raw results (keyed by id) to data/01_raw/openfda_raw.json
4. Transform to RXCUI-keyed format to data/02_intermediate/openfda_by_rxcui.json
   - One id can map to multiple RXCUIs (expanded)
   - One RXCUI can have multiple ids (stored as list)
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from src.knowledge_graph.openfda_data_collection import *


if __name__ == "__main__":
    try:
        # Step 1: Load drug list
        drug_list = load_drug_list()
        
        # Step 2: Fetch raw OpenFDA data
        raw_data = fetch_openfda_raw_data(drug_list)
        
        # # Alternatively, read from json if already fetched to avoid API calls
        # with open("data/01_raw/openfda_raw.json", "r") as f:
        #     raw_data = json.load(f)
        
        # Step 3: Save raw data
        raw_path = save_raw_openfda_data(raw_data)
        
        # Step 4: Transform to RXCUI-keyed format
        rxcui_data = transform_to_rxcui_keyed(raw_data)
        
        # Step 5: Save RXCUI-keyed data
        rxcui_path = save_rxcui_keyed_data(rxcui_data)
        
        # Step 6: Save RXCUI list for filtering
        rxcui_list_path, rxcui_list = save_rxcui_list(rxcui_data)
        
        logger.info("=" * 80)
        logger.info("OpenFDA data extraction and transformation complete!")
        logger.info(f"Raw data: {raw_path}")
        logger.info(f"RXCUI-keyed data: {rxcui_path}")
        logger.info(f"RXCUI list: {rxcui_list_path}")
        logger.info(f"Total unique RXCUIs for top 300 drugs: {len(rxcui_list)}")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise
