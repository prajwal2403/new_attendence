# database.py
import os
from mongoengine import connect, disconnect
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get MongoDB connection string from environment variable
ATLAS_CONNECTION_STRING = os.getenv('MONGODB_ATLAS_CONNECTION_STRING')

def init_db():
    """
    Initialize the MongoDB Atlas connection with retry mechanism.
    """
    if not ATLAS_CONNECTION_STRING:
        logger.error("MongoDB connection string not found in environment variables")
        raise ValueError("MongoDB connection string not configured")

    try:
        # First disconnect any existing connections
        disconnect()
        
        # Connect to MongoDB Atlas with timeout settings
        connect(
            host=ATLAS_CONNECTION_STRING,
            alias='default',
            serverSelectionTimeoutMS=5000,  # 5 second timeout
            connectTimeoutMS=5000,
            retryWrites=True,
            w='majority'
        )
        
        # Test the connection
        from mongoengine.connection import get_db
        db = get_db()
        db.command('ping')
        
        logger.info("Connected to MongoDB Atlas successfully!")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB Atlas: {str(e)}")
        raise