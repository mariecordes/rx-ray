"""
Export RxNorm MySQL tables to Parquet format.

Pipeline:
1. Export raw parquets of RXNCONSO, RXNREL, RXNSAT to data/01_raw/
2. Filter by top 300 RXCUIs and save to data/02_intermediate/
   - For RXNCONSO: Filter by RXCUI column
   - For RXNREL: Filter by RXCUI1 and RXCUI2 columns
   - For RXNSAT: Filter by RXCUI column
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

from src.knowledge_graph.rxnorm_data_collection import *


if __name__ == "__main__":
    try:
        # Step 1: Load RXCUI list from previous script
        rxcui_list = load_rxcui_list()
        
        # Step 2: Export raw parquets
        logger.info("Exporting raw RxNorm tables to Parquet...")
        rxnconso_df, rxnrel_df, rxnsat_df = export_raw_parquets()
        
        # Step 3: Filter by RXCUI list and save
        logger.info("Filtering tables by top 300 RXCUIs...")
        filter_and_save_by_rxcui(rxcui_list)
        
        logger.info("=" * 80)
        logger.info("RxNorm Parquet export and filtering complete!")
        logger.info("Raw tables: data/01_raw/rxn*.parquet")
        logger.info("Filtered tables: data/02_intermediate/rxn*_filtered.parquet")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise
