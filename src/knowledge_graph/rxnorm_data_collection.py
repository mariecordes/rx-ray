import os
import sys
import logging
import pandas as pd
from pathlib import Path
from typing import Set

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from src.knowledge_graph.rxnorm_connector import RxNormConnector
from src.knowledge_graph.rxnorm_extractor import RxNormExtractor


def load_rxcui_list(rxcui_file: str = "data/02_intermediate/top_300_rxcuis.txt") -> Set[str]:
    """
    Load RXCUI list from file.
    
    Args:
        rxcui_file: Path to file with one RXCUI per line
    
    Returns:
        Set of RXCUIs
    """
    logger.info(f"Loading RXCUI list from {rxcui_file}...")
    
    if not os.path.exists(rxcui_file):
        raise FileNotFoundError(f"RXCUI list file not found: {rxcui_file}")
    
    with open(rxcui_file, "r") as f:
        rxcui_list = set(line.strip() for line in f if line.strip())
    
    logger.info(f"Loaded {len(rxcui_list)} RXCUIs")
    return rxcui_list


def export_raw_parquets(output_dir: str = "data/01_raw"):
    """
    Export raw RxNorm tables to Parquet format.
    
    Returns:
        Tuple of (rxnconso_df, rxnrel_df, rxnsat_df)
    """
    logger.info("Connecting to RxNorm database...")
    
    rxnorm_conn = RxNormConnector()
    if not rxnorm_conn.connect():
        raise RuntimeError("Failed to connect to RxNorm database")
    
    try:
        extractor = RxNormExtractor(rxnorm_conn.connection)
        
        # Export RXNCONSO
        logger.info("Exporting RXNCONSO...")
        rxnconso_df = extractor.get_rxnconso_df()
        rxnconso_path = os.path.join(output_dir, "rxnconso_raw.parquet")
        os.makedirs(output_dir, exist_ok=True)
        rxnconso_df.to_parquet(rxnconso_path, compression="snappy", index=False)
        logger.info(f"Exported RXNCONSO: {len(rxnconso_df)} rows -> {rxnconso_path}")
        
        # Export RXNREL
        logger.info("Exporting RXNREL...")
        rxnrel_df = extractor.get_rxnrel_df()
        rxnrel_path = os.path.join(output_dir, "rxnrel_raw.parquet")
        rxnrel_df.to_parquet(rxnrel_path, compression="snappy", index=False)
        logger.info(f"Exported RXNREL: {len(rxnrel_df)} rows -> {rxnrel_path}")
        
        # Export RXNSAT
        logger.info("Exporting RXNSAT...")
        rxnsat_df = extractor.get_rxnsat_df()
        rxnsat_path = os.path.join(output_dir, "rxnsat_raw.parquet")
        rxnsat_df.to_parquet(rxnsat_path, compression="snappy", index=False)
        logger.info(f"Exported RXNSAT: {len(rxnsat_df)} rows -> {rxnsat_path}")
        
        return rxnconso_df, rxnrel_df, rxnsat_df
    
    finally:
        rxnorm_conn.close()


def filter_tables(
    rxnconso_df: pd.DataFrame,
    rxnrel_df: pd.DataFrame,
    rxnsat_df: pd.DataFrame,
    rxcui_list: Set[str]
) -> tuple:
    """
    Filter RxNorm tables by RXCUI list.
    
    Args:
        rxnconso_df: RXNCONSO DataFrame
        rxnrel_df: RXNREL DataFrame
        rxnsat_df: RXNSAT DataFrame
        rxcui_list: Set of RXCUIs to filter by
    
    Returns:
        Tuple of (rxnconso_filtered, rxnrel_filtered, rxnsat_filtered)
    """
    logger.info("Filtering RXNCONSO by RXCUIs...")
    rxnconso_filtered = rxnconso_df[rxnconso_df["RXCUI"].isin(rxcui_list)].copy()
    logger.info(f"Filtered RXNCONSO: {len(rxnconso_filtered)} rows")
    
    logger.info("Filtering RXNREL by RXCUIs...")
    rxnrel_filtered = rxnrel_df[
        rxnrel_df["RXCUI1"].isin(rxcui_list) | rxnrel_df["RXCUI2"].isin(rxcui_list)
    ].copy()
    logger.info(f"Filtered RXNREL: {len(rxnrel_filtered)} rows")
    
    logger.info("Filtering RXNSAT by RXCUIs...")
    rxnsat_filtered = rxnsat_df[rxnsat_df["RXCUI"].isin(rxcui_list)].copy()
    logger.info(f"Filtered RXNSAT: {len(rxnsat_filtered)} rows")
    
    return rxnconso_filtered, rxnrel_filtered, rxnsat_filtered


def filter_and_save_by_rxcui(
    rxcui_list: Set[str],
    input_dir: str = "data/01_raw",
    output_dir: str = "data/02_intermediate"
) -> tuple:
    """
    Load raw parquets, filter by RXCUI list, and save filtered parquets.
    
    Args:
        rxcui_list: Set of RXCUIs to filter by
        input_dir: Directory containing raw parquet files
        output_dir: Output directory for filtered parquets
    
    Returns:
        Tuple of (rxnconso_filtered, rxnrel_filtered, rxnsat_filtered)
    """
    # Load raw parquets
    rxnconso_df, rxnrel_df, rxnsat_df = load_raw_parquets(input_dir)
    
    # Filter tables
    rxnconso_filtered, rxnrel_filtered, rxnsat_filtered = filter_tables(
        rxnconso_df, rxnrel_df, rxnsat_df, rxcui_list
    )
    
    # Save filtered parquets
    os.makedirs(output_dir, exist_ok=True)
    
    rxnconso_path = os.path.join(output_dir, "rxnconso_filtered.parquet")
    rxnconso_filtered.to_parquet(rxnconso_path, compression="snappy", index=False)
    logger.info(f"Saved filtered RXNCONSO -> {rxnconso_path}")
    
    rxnrel_path = os.path.join(output_dir, "rxnrel_filtered.parquet")
    rxnrel_filtered.to_parquet(rxnrel_path, compression="snappy", index=False)
    logger.info(f"Saved filtered RXNREL -> {rxnrel_path}")
    
    rxnsat_path = os.path.join(output_dir, "rxnsat_filtered.parquet")
    rxnsat_filtered.to_parquet(rxnsat_path, compression="snappy", index=False)
    logger.info(f"Saved filtered RXNSAT -> {rxnsat_path}")
    
    # Log statistics
    logger.info("=" * 80)
    logger.info("Filtering Statistics:")
    logger.info(f"Total RXCUIs in filter list: {len(rxcui_list)}")
    logger.info(f"RXNCONSO: {len(rxnconso_df)} -> {len(rxnconso_filtered)} rows ({100*len(rxnconso_filtered)/len(rxnconso_df):.1f}%)")
    logger.info(f"RXNREL: {len(rxnrel_df)} -> {len(rxnrel_filtered)} rows ({100*len(rxnrel_filtered)/len(rxnrel_df):.1f}%)")
    logger.info(f"RXNSAT: {len(rxnsat_df)} -> {len(rxnsat_filtered)} rows ({100*len(rxnsat_filtered)/len(rxnsat_df):.1f}%)")
    logger.info("=" * 80)
    
    return rxnconso_filtered, rxnrel_filtered, rxnsat_filtered


def load_raw_parquets(input_dir: str = "data/01_raw"):
    """
    Load raw RxNorm parquets from disk.
    
    Args:
        input_dir: Directory containing raw parquet files
    
    Returns:
        Tuple of (rxnconso_df, rxnrel_df, rxnsat_df)
    """
    logger.info(f"Loading raw parquets from {input_dir}...")
    
    rxnconso_path = os.path.join(input_dir, "rxnconso_raw.parquet")
    rxnrel_path = os.path.join(input_dir, "rxnrel_raw.parquet")
    rxnsat_path = os.path.join(input_dir, "rxnsat_raw.parquet")
    
    if not all(os.path.exists(p) for p in [rxnconso_path, rxnrel_path, rxnsat_path]):
        raise FileNotFoundError(f"One or more raw parquet files not found in {input_dir}")
    
    rxnconso_df = pd.read_parquet(rxnconso_path)
    logger.info(f"Loaded RXNCONSO: {len(rxnconso_df)} rows")
    
    rxnrel_df = pd.read_parquet(rxnrel_path)
    logger.info(f"Loaded RXNREL: {len(rxnrel_df)} rows")
    
    rxnsat_df = pd.read_parquet(rxnsat_path)
    logger.info(f"Loaded RXNSAT: {len(rxnsat_df)} rows")
    
    return rxnconso_df, rxnrel_df, rxnsat_df


def load_filtered_parquets(input_dir: str = "data/02_intermediate"):
    """
    Load filtered RxNorm parquets from disk.
    
    Args:
        input_dir: Directory containing filtered parquet files
    
    Returns:
        Tuple of (rxnconso_filtered_df, rxnrel_filtered_df, rxnsat_filtered_df)
    """
    logger.info(f"Loading filtered parquets from {input_dir}...")
    
    rxnconso_path = os.path.join(input_dir, "rxnconso_filtered.parquet")
    rxnrel_path = os.path.join(input_dir, "rxnrel_filtered.parquet")
    rxnsat_path = os.path.join(input_dir, "rxnsat_filtered.parquet")
    
    if not all(os.path.exists(p) for p in [rxnconso_path, rxnrel_path, rxnsat_path]):
        raise FileNotFoundError(f"One or more filtered parquet files not found in {input_dir}")
    
    rxnconso_df = pd.read_parquet(rxnconso_path)
    logger.info(f"Loaded filtered RXNCONSO: {len(rxnconso_df)} rows")
    
    rxnrel_df = pd.read_parquet(rxnrel_path)
    logger.info(f"Loaded filtered RXNREL: {len(rxnrel_df)} rows")
    
    rxnsat_df = pd.read_parquet(rxnsat_path)
    logger.info(f"Loaded filtered RXNSAT: {len(rxnsat_df)} rows")
    
    return rxnconso_df, rxnrel_df, rxnsat_df
