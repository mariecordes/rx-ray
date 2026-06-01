import os
import logging
import json
import requests
import time
from typing import Dict, Any, Optional

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
    
    def __init__(self, base_url: str = None, timeout: int = 10, delay: float = 0.5):
        self.base_url = os.getenv("OPENFDA_BASE_URL", base_url)
        self.timeout = timeout
        self.delay = delay
        self.session = requests.Session()
    
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
    
    def fetch_by_rxcui(self, rxcui: str) -> Optional[Dict[str, Any]]:
        """
        Fetch drug label by RxNorm Concept ID.
        
        Args:
            rxcui: RxNorm Concept ID
        
        Returns:
            First matching label dict, or None if not found
        """
        try:
            params = {
                "search": f"openfda.rxcui:{rxcui}",
                "limit": 1
            }
            
            response = self.session.get(
                self.base_url,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            results = data.get("results", [])
            
            if results:
                logger.info(f"Found label for RXCUI {rxcui}")
                return results[0]
            else:
                logger.warning(f"No OpenFDA label for RXCUI {rxcui}")
                return None
        
        except requests.exceptions.RequestException as e:
            logger.error(f"API error for RXCUI {rxcui}: {e}")
            return None
        
        finally:
            time.sleep(self.delay)
            
        
    def extract_structured_fields(self, label: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract relevant structured fields from an OpenFDA label for knowledge graph building.
        
        Only extracts fields relevant to medication safety, interactions, and side effects.
        Skips clinical details, device info, and metadata fields.
        
        Args:
            label: Raw label dict from API
        
        Returns:
            Structured dict with organized label data (only relevant fields)
        """
        # TIER 1: Core metadata
        structured = {
            "rxcui": label.get("openfda", {}).get("rxcui", [""])[0],
            "brand_names": label.get("openfda", {}).get("brand_name", []),
            "generic_name": label.get("openfda", {}).get("generic_name", [""])[0],
            "manufacturer": label.get("openfda", {}).get("manufacturer_name", [""])[0],
            "route": label.get("openfda", {}).get("route", [""])[0],
            "product_type": label.get("openfda", {}).get("product_type", [""])[0],
            "ndc_codes": label.get("openfda", {}).get("product_ndc", []),
            "substance_name": label.get("openfda", {}).get("substance_name", [""])[0],
            "description": label.get("description", [""])[0],
            "package_label_principal_display_panel": label.get("package_label_principal_display_panel", [""])[0],
        }
        
        # TIER 1: Safety & Clinical Information (most important for KG)
        safety_sections = {
            # Indications: what the drug treats
            "indications_and_usage": label.get("indications_and_usage", []),
            
            # Safety warnings (in priority order)
            "boxed_warning": label.get("boxed_warning", []),  # Strongest FDA warning
            # Combine "warnings" and "warnings_and_cautions" if both exist
            "warnings": label.get("warnings_and_cautions", []) + label.get("warnings", []),
            "contraindications": label.get("contraindications", []),
            "do_not_use": label.get("do_not_use", []),
            
            # Side effects & adverse reactions
            "adverse_reactions": label.get("adverse_reactions", []),
            
            # Drug-drug interactions
            "drug_interactions": label.get("drug_interactions", []),
            
            # Ingredients
            "active_ingredient": label.get("active_ingredient", []),
            "inactive_ingredient": label.get("inactive_ingredient", []),
        }
        
        # TIER 2: Precautions & Population-Specific (secondary priority)
        precautions_sections = {
            "ask_doctor": label.get("ask_doctor", []),
            "ask_doctor_or_pharmacist": label.get("ask_doctor_or_pharmacist", []),
            "precautions": label.get("precautions", []),
            "general_precautions": label.get("general_precautions", []),
            
            # Population-specific warnings
            "use_in_specific_populations": label.get("use_in_specific_populations", []),
            "pregnancy_or_breast_feeding": label.get("pregnancy_or_breast_feeding", []),
            "pregnancy": label.get("pregnancy", []),
            "nursing_mothers": label.get("nursing_mothers", []),
            "labor_and_delivery": label.get("labor_and_delivery", []),
            "pediatric_use": label.get("pediatric_use", []),
            "geriatric_use": label.get("geriatric_use", []),
            
            # Overdose information
            "drug_abuse_and_dependence": label.get("drug_abuse_and_dependence", []),
            "controlled_substance": label.get("controlled_substance", []),
            "abuse": label.get("abuse", []),
            "dependence": label.get("dependence", []),
            "overdosage": label.get("overdosage", []),
            
            # Usage instructions
            "dosage_and_administration": label.get("dosage_and_administration", []),
            "dosage_forms_and_strengths": label.get("dosage_forms_and_strengths", []),
            "stop_use": label.get("stop_use", []),
            "information_for_patients": label.get("information_for_patients", []),
        }
        
        # Combine sections
        structured["safety_sections"] = safety_sections
        structured["precautions_sections"] = precautions_sections
        
        # Optional: Store raw how_supplied for reference (shows available formulations)
        structured["how_supplied"] = label.get("how_supplied", [])
        
        return structured
    
    def extract_entities_from_label(self, structured_label: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract key entities (side effects, contraindications, interactions) from unstructured label text.
        
        This is a basic implementation using patterns and heuristics.
        For production, consider using NER or LLM enhancement.
        
        Args:
            structured_label: Output from extract_structured_fields()
        
        Returns:
            Dict with extracted entities:
            {
                "side_effects": [...],
                "contraindications": [...],
                "interactions": [...],
                "warnings": {...}
            }
        """
        extracted = {
            "side_effects": [],
            "contraindications": [],
            "interactions": [],
            "warnings": {
                "boxed": len(structured_label["safety_sections"].get("boxed_warning", [])) > 0,
                "pregnancy": False,
                "renal_impairment": False,
                "hepatic_impairment": False,
                "pediatric": False,
                "geriatric": False,
                "substance_abuse": False,
                "substance_dependence": False,
            }
        }
        
        # Extract side effects from adverse_reactions
        adverse_rxns = structured_label["safety_sections"].get("adverse_reactions", [])
        if adverse_rxns:
            for reaction in adverse_rxns:
                if isinstance(reaction, str):
                    # Split on common delimiters and extract terms
                    terms = [t.strip() for t in reaction.split(';')]
                    extracted["side_effects"].extend(terms)
        
        # Extract contraindications
        contraindications = structured_label["safety_sections"].get("contraindications", [])
        if contraindications:
            for contra in contraindications:
                if isinstance(contra, str):
                    extracted["contraindications"].append(contra)
        
        # Extract interactions from drug_interactions section
        interactions = structured_label["safety_sections"].get("drug_interactions", [])
        if interactions:
            for inter in interactions:
                if isinstance(inter, str):
                    extracted["interactions"].append(inter)
        
        # Flag warnings based on text presence from safety sections
        warnings_text = " ".join(structured_label["safety_sections"].get("warnings", []))
        
        # Check precautions sections for population-specific warnings
        pregnancy_text = " ".join(structured_label["precautions_sections"].get("pregnancy_or_breast_feeding", []))
        use_in_populations = " ".join(structured_label["precautions_sections"].get("use_in_specific_populations", []))
        patient_info = " ".join(structured_label["precautions_sections"].get("information_for_patients", []))
        
        # Pregnancy warning (check multiple sources)
        if any(term in pregnancy_text.lower() for term in ["pregnancy", "pregnant", "gestation"]) or \
           any(term in use_in_populations.lower() for term in ["pregnancy", "pregnant"]):
            extracted["warnings"]["pregnancy"] = True
        
        # Renal/kidney impairment
        if any(term in warnings_text.lower() for term in ["renal", "kidney", "creatinine"]):
            extracted["warnings"]["renal_impairment"] = True
        
        # Hepatic/liver impairment
        if any(term in warnings_text.lower() for term in ["hepatic", "liver", "cirrhosis"]):
            extracted["warnings"]["hepatic_impairment"] = True
        
        # Pediatric warnings (check multiple sources)
        if any(term in warnings_text.lower() for term in ["pediatric", "children", "child", "infant"]) or \
           any(term in use_in_populations.lower() for term in ["pediatric", "children"]):
            extracted["warnings"]["pediatric"] = True
        
        # Geriatric warnings (check multiple sources)
        if any(term in warnings_text.lower() for term in ["geriatric", "elderly", "older", "aged"]) or \
           any(term in use_in_populations.lower() for term in ["geriatric", "elderly"]):
            extracted["warnings"]["geriatric"] = True
        
        # Substance abuse and dependence warnings
        abuse_text = " ".join(structured_label["precautions_sections"].get("drug_abuse_and_dependence", []) +
                              structured_label["precautions_sections"].get("abuse", []))
        if abuse_text and "abuse" in abuse_text.lower():
            extracted["warnings"]["substance_abuse"] = True
        
        dependence_text = " ".join(structured_label["precautions_sections"].get("dependence", []))
        if dependence_text and "dependence" in dependence_text.lower():
            extracted["warnings"]["substance_dependence"] = True
        
        return extracted
    
    
    # def parse_warnings_text(self, warnings_text: str) -> Dict[str, Any]:
    #     """
    #     Parse unstructured warnings text to extract key information.
        
    #     This is a basic implementation using pattern matching.
    #     For production, consider using NER or LLM.
        
    #     Args:
    #         warnings_text: Raw warning text from label
        
    #     Returns:
    #         Dict with extracted warning types and severity
    #     """
    #     warnings_parsed = {
    #         "reye_syndrome": False,
    #         "allergy_alert": False,
    #         "stomach_bleeding": False,
    #         "pregnancy_warning": False,
    #         "raw_text": warnings_text[:500]  # First 500 chars
    #     }
        
    #     text_lower = warnings_text.lower()
        
    #     if "reye's syndrome" in text_lower or "reye syndrome" in text_lower:
    #         warnings_parsed["reye_syndrome"] = True
        
    #     if "allergy" in text_lower or "allergic reaction" in text_lower:
    #         warnings_parsed["allergy_alert"] = True
        
    #     if "stomach" in text_lower and ("bleed" in text_lower or "ulcer" in text_lower):
    #         warnings_parsed["stomach_bleeding"] = True
        
    #     if "pregnant" in text_lower or "pregnancy" in text_lower:
    #         warnings_parsed["pregnancy_warning"] = True
        
    #     return warnings_parsed
    
    def test_api(self, drug_name: str = "aspirin") -> Optional[dict]:
        """Test OpenFDA API with a simple query."""
        try:
            params = {
                "search": f"openfda.generic_name:{drug_name}",
                "limit": 1
            }
            
            logger.info(f"Querying OpenFDA API for '{drug_name}'...")
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            total = data.get("meta", {}).get("results", {}).get("total", 0)
            
            if total > 0:
                logger.info(f"OpenFDA API working. Found {total} result(s) for '{drug_name}'")
                result = data["results"][0]
                logger.info(f"  - Brand: {result.get('openfda', {}).get('brand_name', ['N/A'])[0]}")
                logger.info(f"  - Generic: {result.get('openfda', {}).get('generic_name', ['N/A'])[0]}")
                logger.info(f"  - Manufacturer: {result.get('openfda', {}).get('manufacturer_name', ['N/A'])[0]}")
                return result
            else:
                logger.warning(f"No OpenFDA results for '{drug_name}'")
                return None
        
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenFDA API request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenFDA response: {e}")
            return None
    
    def test_rxcui_search(self, rxcui: str) -> Optional[dict]:
        """Test OpenFDA search by RXCUI."""
        try:
            params = {
                "search": f"openfda.rxcui:{rxcui}",
                "limit": 1
            }
            
            logger.info(f"Querying OpenFDA API by RXCUI: {rxcui}...")
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            total = data.get("meta", {}).get("results", {}).get("total", 0)
            
            if total > 0:
                logger.info(f"Found {total} label(s) for RXCUI {rxcui}")
                return data["results"][0]
            else:
                logger.warning(f"No OpenFDA labels for RXCUI {rxcui}")
                return None
        
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenFDA API request failed: {e}")
            return None


if __name__ == "__main__":
    pass
