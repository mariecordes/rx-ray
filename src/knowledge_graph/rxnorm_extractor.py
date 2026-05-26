import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class RxNormExtractor:
    """Extract drug concepts and relationships from RxNorm."""
    
    def __init__(self, mysql_connection):
        """
        Initialize with MySQL connection.
        
        Args:
            mysql_connection: Active mysql.connector connection
        """
        self.conn = mysql_connection
    
    def find_drug_rxcui(self, drug_name: str) -> Optional[str]:
        """
        Find RXCUI for a drug by name.
        
        Priority: RxNorm → SNOMEDCT → others
        Prefer generic names (GCN, GPCK) over brand names (BN)
        
        Args:
            drug_name: Drug name to search for
        
        Returns:
            RXCUI if found, else None
        """
        try:
            cursor = self.conn.cursor(dictionary=True)
            
            # Query for the drug, prioritizing RxNorm and generic names
            query = """
            SELECT RXCUI, STR, TTY, SAB
            FROM rxnconso
            WHERE LOWER(STR) = %s
            ORDER BY 
                CASE WHEN SAB = 'RXNORM' THEN 0 ELSE 1 END,
                CASE WHEN TTY IN ('SCD', 'GCN') THEN 0 ELSE 1 END
            LIMIT 1
            """
            
            cursor.execute(query, (drug_name.lower(),))
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return result["RXCUI"]
            return None
        
        except Exception as e:
            logger.error(f"Error finding RXCUI for '{drug_name}': {e}")
            return None
        
    def get_ingredients(self, rxcui: str) -> List[Dict[str, Any]]:
        """
        Get ingredients of a drug.
        
        Args:
            rxcui: RxNorm Concept ID
        
        Returns:
            List of drug dicts with rxcui, name, etc.
        """
        try:
            cursor = self.conn.cursor(dictionary=True)
            
            # Query for has_ingredient relationships
            query = """
            SELECT 
                r.RXCUI2 as ingredient_rxcui,
                c.STR as ingredient_name,
                c.TTY as term_type,
                r.RELA as relationship
            FROM rxnrel r
            JOIN rxnconso c ON r.RXCUI2 = c.RXCUI
            WHERE r.RXCUI1 = %s
              AND r.RELA IN ('ingredient_of', 'ingredients_of', 'active_ingredient_of', 'precise_ingredient_of', 'inactive_ingredient_of')
            """
            
            cursor.execute(query, (rxcui,))
            results = cursor.fetchall()
            cursor.close()
            
            ingredients = []
            for row in results:
                ingredients.append({
                    "rxcui": row["ingredient_rxcui"],
                    "name": row["ingredient_name"],
                    "term_type": row["term_type"]
                })
            
            return ingredients
        
        except Exception as e:
            logger.error(f"Error getting ingredients for RXCUI {rxcui}: {e}")
            return []
    
    def is_ingredient_of(self, rxcui: str) -> List[Dict[str, Any]]:
        """
        Get drugs of which a concept is an ingredient.
        
        Args:
            rxcui: RxNorm Concept ID
        
        Returns:
            List of drug dicts with rxcui, name, etc.
        """
        try:
            cursor = self.conn.cursor(dictionary=True)
            
            # Query for has_ingredient relationships
            query = """
            SELECT 
                r.RXCUI2 as concept_rxcui,
                c.STR as concept_name,
                c.TTY as term_type,
                r.RELA as relationship
            FROM rxnrel r
            JOIN rxnconso c ON r.RXCUI2 = c.RXCUI
            WHERE r.RXCUI1 = %s
              AND r.RELA IN ('has_ingredient', 'has_ingredients', 'has_active_ingredient', 'has_precise_ingredient')
            """
            
            cursor.execute(query, (rxcui,))
            results = cursor.fetchall()
            cursor.close()
            
            concepts = []
            for row in results:
                concepts.append({
                    "rxcui": row["concept_rxcui"],
                    "name": row["concept_name"],
                    "term_type": row["term_type"]
                })
            
            return concepts
        
        except Exception as e:
            logger.error(f"Error getting ingredients for RXCUI {rxcui}: {e}")
            return []
    
    def get_aliases(self, rxcui: str) -> List[str]:
        """
        Get alternative names (aliases) for a drug.
        
        Args:
            rxcui: RxNorm Concept ID
        
        Returns:
            List of alternative names
        """
        try:
            cursor = self.conn.cursor(dictionary=True)
            
            # Query for all names associated with this concept
            query = """
            SELECT DISTINCT STR
            FROM rxnconso
            WHERE RXCUI = %s
              AND SAB = 'RXNORM'
            LIMIT 10
            """
            
            cursor.execute(query, (rxcui,))
            results = cursor.fetchall()
            cursor.close()
            
            aliases = [row["STR"] for row in results]
            return aliases
        
        except Exception as e:
            logger.error(f"Error getting aliases for RXCUI {rxcui}: {e}")
            return []
    
    def extract_drug(self, drug_name: str) -> Optional[Dict[str, Any]]:
        """
        Extract complete drug information from RxNorm.
        
        Args:
            drug_name: Drug name
        
        Returns:
            Drug dict with rxcui, name, ingredients, class, aliases
        """
        # Find RXCUI
        rxcui = self.find_drug_rxcui(drug_name)
        if not rxcui:
            logger.warning(f"Drug not found in RxNorm: {drug_name}")
            return None
        
        logger.info(f"Found: {drug_name} (RXCUI: {rxcui})")
        
        # Extract related data
        ingredients = self.get_ingredients(rxcui)
        ingredient_of = self.is_ingredient_of(rxcui)
        aliases = self.get_aliases(rxcui)
        
        print(ingredient_of)
        
        drug_data = {
            "name": drug_name,
            "rxcui": rxcui,
            "ingredients": ingredients,
            "ingredient_of": ingredient_of,
            "aliases": aliases,
            "source": "rxnorm"
        }
        
        return drug_data


if __name__ == "__main__":
    pass
