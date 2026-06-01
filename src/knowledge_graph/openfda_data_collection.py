import os
import sys
import json
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from src.knowledge_graph.openfda_connector import OpenFDAConnector


def load_drug_list() -> List[str]:
    """
    Load and process the top 300 drugs list.
    
    Returns:
        List of unique drug names (split and deduplicated)
    """
    logger.info("Loading top 300 drugs list...")
    top_300_drugs = pd.read_csv("data/raw/clincalc_top_300_drugs_2023.csv")
    drug_list_raw = top_300_drugs.drug_name.to_list()
    
    logger.info(f"Initial number of drug entries: {len(drug_list_raw)}")
    
    # Separate entries with ";" into individual drugs
    for drug in drug_list_raw[:]:  # Iterate over a copy
        if ";" in drug:
            drugs = [d.strip() for d in drug.split(";")]
            drug_list_raw.extend(drugs)
            drug_list_raw.remove(drug)
    
    logger.info(f"Number of drug entries after splitting: {len(drug_list_raw)}")
    
    # Remove duplicates and empty strings
    drug_list_raw = list(set([d.strip() for d in drug_list_raw if d.strip()]))
    logger.info(f"Number of unique drug entries after deduplication: {len(drug_list_raw)}")
    
    return sorted(drug_list_raw)


def fetch_openfda_raw_data(drug_list: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Fetch OpenFDA API results for all drugs.
    
    Returns:
        Dict with OpenFDA result id as key and full result as value
    """
    logger.info("Fetching OpenFDA data...")
    openfda_connector = OpenFDAConnector()  
    
    raw_data = {}
    total_results = 0
    
    for i, drug in enumerate(drug_list, 1):
        logger.info(f"[{i}/{len(drug_list)}] Querying OpenFDA for '{drug}'...")
        
        try:
            results = openfda_connector.query_api_for_generic_name(drug, search_limit=1000)
            
            for result in results:
                # Use the id field as key if available, otherwise generate one
                result_id = result.get("id", f"drug_{drug}_{len(raw_data)}")
                raw_data[result_id] = result
                total_results += 1
            
            logger.info(f"  Found {len(results)} result(s)")
        
        except Exception as e:
            logger.error(f"Error fetching data for '{drug}': {e}")
            continue
    
    logger.info(f"Total API results fetched: {total_results}")
    return raw_data


def save_raw_openfda_data(raw_data: Dict[str, Dict[str, Any]], output_dir: str = "data/01_raw", sample: bool = False) -> str:
    """Save raw OpenFDA data to JSON."""
    os.makedirs(output_dir, exist_ok=True)
    
    file_name = "openfda_raw_sample.json" if sample else "openfda_raw.json"
    output_path = os.path.join(output_dir, file_name)
    
    logger.info(f"Saving raw OpenFDA data to {output_path}...")
    
    with open(output_path, "w") as f:
        json.dump(raw_data, f, indent=2, default=str)
    
    logger.info(f"Saved {len(raw_data)} raw results")
    return output_path


def transform_to_rxcui_keyed(raw_data: Dict[str, Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Transform raw OpenFDA data from id-keyed to RXCUI-keyed format.
    
    - One id can map to multiple RXCUIs (expanded as separate entries)
    - One RXCUI can have multiple ids (stored as list of dicts)
    
    Returns:
        Dict with RXCUI as key and list of result dicts as value
    """
    logger.info("Transforming OpenFDA data to RXCUI-keyed format...")
    
    rxcui_data = {}
    results_processed = 0
    results_with_rxcui = 0
    rxcuis_found = 0
    
    for result_id, result in raw_data.items():
        results_processed += 1
        
        # Extract RXCUI(s) from openfda field
        rxcuis = result.get("openfda", {}).get("rxcui", [])
        
        if not rxcuis:
            continue
        
        results_with_rxcui += 1
        
        # Handle case where rxcui is a list
        if isinstance(rxcuis, str):
            rxcuis = [rxcuis]
        
        for rxcui in rxcuis:
            rxcuis_found += 1
            
            # Remove the openfda.rxcui from the result to avoid redundancy
            result_copy = result.copy()
            result_copy_rxcui = result_copy.get("openfda", {})
            
            if "rxcui" in result_copy_rxcui:
                del result_copy_rxcui["rxcui"]
            
            # Initialize list for this RXCUI if not present
            if rxcui not in rxcui_data:
                rxcui_data[rxcui] = []
            
            # Append result dict to the list for this RXCUI
            rxcui_data[rxcui].append({
                "source_id": result_id,  # Track origin
                "data": result_copy
            })
    
    logger.info(f"Processed {results_processed} raw results")
    logger.info(f"Found {results_with_rxcui} results with RXCUI(s)")
    logger.info(f"Expanded to {rxcuis_found} individual RXCUI-result pairs")
    logger.info(f"Total unique RXCUIs: {len(rxcui_data)}")
    
    # Log distribution of results per RXCUI
    results_per_rxcui = [len(v) for v in rxcui_data.values()]
    logger.info(f"Results per RXCUI - Min: {min(results_per_rxcui)}, Max: {max(results_per_rxcui)}, Avg: {sum(results_per_rxcui)/len(results_per_rxcui):.1f}")
    
    multi_result_rxcuis = sum(1 for v in rxcui_data.values() if len(v) > 1)
    logger.info(f"RXCUIs with multiple results: {multi_result_rxcuis}")
    
    return rxcui_data


def save_rxcui_keyed_data(rxcui_data: Dict[str, List[Dict[str, Any]]], output_dir: str = "data/02_intermediate", sample: bool = False):
    """Save RXCUI-keyed OpenFDA data to JSON."""
    os.makedirs(output_dir, exist_ok=True)
    
    file_name = "openfda_by_rxcui_sample.json" if sample else "openfda_by_rxcui.json"
    output_path = os.path.join(output_dir, file_name)
    
    logger.info(f"Saving RXCUI-keyed OpenFDA data to {output_path}...")
    
    # Convert to serializable format
    serializable_data = {}
    for rxcui, results in rxcui_data.items():
        serializable_data[str(rxcui)] = results
    
    with open(output_path, "w") as f:
        json.dump(serializable_data, f, indent=2, default=str)
    
    logger.info(f"Saved {len(rxcui_data)} unique RXCUIs")
    return output_path


def save_rxcui_list(rxcui_data: Dict[str, List[Dict[str, Any]]], output_dir: str = "data/02_intermediate", sample: bool = False):
    """Save the list of RXCUIs to a file for later filtering."""
    os.makedirs(output_dir, exist_ok=True)
    
    
    file_name = "top_300_rxcuis_sample.txt" if sample else "top_300_rxcuis.txt"
    output_path = os.path.join(output_dir, file_name)
    
    logger.info(f"Saving RXCUI list to {output_path}...")
    
    rxcui_list = sorted(rxcui_data.keys())
    with open(output_path, "w") as f:
        for rxcui in rxcui_list:
            f.write(f"{rxcui}\n")
    
    logger.info(f"Saved {len(rxcui_list)} unique RXCUIs")
    return output_path, rxcui_list
