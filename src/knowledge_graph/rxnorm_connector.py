import os
import sys
import logging
from pathlib import Path
from typing import Optional

import mysql.connector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# # Add project root to path
# project_root = Path(__file__).parent.parent
# sys.path.insert(0, str(project_root))

# Load environment variables from .env file
from dotenv import load_dotenv  # type: ignore
load_dotenv()


class RxNormConnector:
    """Test MySQL connection to RxNorm database."""
    
    def __init__(self, host: str = None, user: str = None, password: str = None, database: str = None):
        
        rxnorm_config = {
            "host": os.getenv("RXNORM_HOST", host or "localhost"),
            "user": os.getenv("RXNORM_USER", user or "root"),
            "password": os.getenv("RXNORM_PASSWORD", password or ""),
            "database": os.getenv("RXNORM_DATABASE", database or "rxnorm"),
        }

        self.host = host or rxnorm_config["host"]
        self.user = user or rxnorm_config["user"]
        self.password = password or rxnorm_config["password"]
        self.database = database or rxnorm_config["database"]
        self.connection = None
    
    def connect(self) -> bool:
        """Test connection to RxNorm MySQL database."""
        try:
            import mysql.connector
            
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            
            if self.connection.is_connected():
                logger.info("Connected to RxNorm MySQL database")
                return True
        except Exception as e:
            logger.error(f"Failed to connect to RxNorm: {e}")
            logger.info("  Make sure mysql-connector-python is installed: pip install mysql-connector-python")
            return False
    
    def test_query(self, drug_name: str = "aspirin") -> Optional[dict]:
        """Test a simple query to find a drug concept."""
        if not self.connection or not self.connection.is_connected():
            logger.warning("No active connection")
            return None
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            # Query RXNCONSO for the drug
            query = """
            SELECT RXCUI, STR, TTY, SAB 
            FROM rxnconso 
            WHERE LOWER(STR) = %s 
            LIMIT 5
            """
            
            cursor.execute(query, (drug_name.lower(),))
            results = cursor.fetchall()
            cursor.close()
            
            if results:
                logger.info(f"Found {len(results)} result(s) for '{drug_name}':")
                for row in results:
                    logger.info(f"  - {row['STR']} (RXCUI: {row['RXCUI']}, TTY: {row['TTY']})")
                return results[0]
            else:
                logger.warning(f"No results found for '{drug_name}'")
                return None
        
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return None
    
    def close(self):
        """Close database connection."""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("Database connection closed")

