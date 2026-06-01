import logging
from typing import List, Dict, Any, Optional
import pandas as pd

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
    
    def get_rxnconso_df(self) -> pd.DataFrame:
        """
        Get entire RXNCONSO table as a pandas DataFrame.
        
        Returns:
            DataFrame with all RXNCONSO records
        """
        try:
            query = "SELECT * FROM rxnconso"
            df = pd.read_sql(query, self.conn)
            logger.info(f"Loaded RXNCONSO: {len(df)} rows")
            return df
        except Exception as e:
            logger.error(f"Error loading RXNCONSO: {e}")
            return pd.DataFrame()
    
    def get_rxnrel_df(self) -> pd.DataFrame:
        """
        Get entire RXNREL table as a pandas DataFrame.
        
        Returns:
            DataFrame with all RXNREL records
        """
        try:
            query = "SELECT * FROM rxnrel"
            df = pd.read_sql(query, self.conn)
            logger.info(f"Loaded RXNREL: {len(df)} rows")
            return df
        except Exception as e:
            logger.error(f"Error loading RXNREL: {e}")
            return pd.DataFrame()
    
    def get_rxnsat_df(self) -> pd.DataFrame:
        """
        Get entire RXNSAT table as a pandas DataFrame.
        
        Returns:
            DataFrame with all RXNSAT records
        """
        try:
            query = "SELECT * FROM rxnsat"
            df = pd.read_sql(query, self.conn)
            logger.info(f"Loaded RXNSAT: {len(df)} rows")
            return df
        except Exception as e:
            logger.error(f"Error loading RXNSAT: {e}")
            return pd.DataFrame()
    
    def get_rxnrel_with_drug_names(self) -> pd.DataFrame:
        """
        Return RXNREL relationships with appended drug names for both RXCUI1 and RXCUI2.

        The RXNREL table contains relationships between RXCUI1 and RXCUI2, but not
        the actual drug names. This function joins RXNREL to RXNCONSO twice to append
        preferred names for both concepts.

        Preferred-name logic:
        - Prefer RXNORM source names
        - Prefer English terms
        - Prefer non-suppressed terms
        - Prefer current prescribable content when available
        - Prefer clinically useful term types such as SCD, SBD, IN, PIN, MIN, BN

        Returns:
            pandas DataFrame with RXCUI1, RXCUI1_NAME, RXCUI1_TTY, RELA,
            RXCUI2, RXCUI2_NAME, RXCUI2_TTY.
            Returns an empty DataFrame if an error occurs.
        """
        try:
            query = """
            WITH preferred_names AS (
                SELECT
                    RXCUI,
                    STR,
                    TTY,
                    SAB,
                    SUPPRESS,
                    CVF,
                    ROW_NUMBER() OVER (
                        PARTITION BY RXCUI
                        ORDER BY
                            CASE WHEN SAB = 'RXNORM' THEN 0 ELSE 1 END,
                            CASE WHEN LAT = 'ENG' THEN 0 ELSE 1 END,
                            CASE WHEN SUPPRESS = 'N' THEN 0 ELSE 1 END,
                            CASE WHEN CVF = '4096' THEN 0 ELSE 1 END,
                            CASE TTY
                                WHEN 'SCD' THEN 1
                                WHEN 'SBD' THEN 2
                                WHEN 'IN'  THEN 3
                                WHEN 'PIN' THEN 4
                                WHEN 'MIN' THEN 5
                                WHEN 'BN'  THEN 6
                                WHEN 'SCDF' THEN 7
                                WHEN 'SBDF' THEN 8
                                WHEN 'SCDC' THEN 9
                                WHEN 'SBDC' THEN 10
                                ELSE 99
                            END,
                            LENGTH(STR),
                            STR
                    ) AS rn
                FROM rxnconso
                WHERE RXCUI IS NOT NULL
                AND STR IS NOT NULL
                AND LAT = 'ENG'
                AND SUPPRESS = 'N'
            )
            SELECT
                r.RXCUI1,
                n1.STR AS RXCUI1_NAME,
                n1.TTY AS RXCUI1_TTY,

                r.RELA,

                r.RXCUI2,
                n2.STR AS RXCUI2_NAME,
                n2.TTY AS RXCUI2_TTY
            FROM rxnrel r
            JOIN preferred_names n1
                ON r.RXCUI1 = n1.RXCUI
            AND n1.rn = 1
            JOIN preferred_names n2
                ON r.RXCUI2 = n2.RXCUI
            AND n2.rn = 1
            WHERE r.RXCUI1 IS NOT NULL
            AND r.RXCUI2 IS NOT NULL
            """

            df = pd.read_sql(query, self.conn)
            return df

        except Exception as e:
            logger.error(f"Error getting RXNREL relationships with drug names: {e}")
            return pd.DataFrame()


if __name__ == "__main__":
    pass
