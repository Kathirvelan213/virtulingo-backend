import os
from supabase import create_client, Client, ClientOptions
from dotenv import load_dotenv
from typing import Optional, Dict, List, Any
import logging
import ssl

import asyncpg

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class SupabaseConnection:
    """
    Singleton Supabase client manager.
    Provides a centralized Supabase client for all database operations.
    """
    
    _instance: Optional['SupabaseConnection'] = None
    _client: Optional[Client] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SupabaseConnection, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Supabase client using NEW authentication system (Publishable/Secret keys)."""
        try:
            url = os.getenv('SUPABASE_URL')
            
            # NEW Authentication System:
            # - Publishable Key (sb_publishable_*): For client-side with RLS
            # - Secret Key (sb_secret_*): For backend with privileged access
            secret_key = os.getenv('SUPABASE_SECRET_KEY')  # sb_secret_*
            publishable_key = os.getenv('SUPABASE_PUBLISHABLE_KEY')  # sb_publishable_*
            
            if not url:
                raise ValueError("SUPABASE_URL must be set in environment variables")
            
            # For backend operations, use SECRET KEY (privileged access)
            if not secret_key:
                raise ValueError("SUPABASE_SECRET_KEY is required for backend operations")
            
            # Initialize with secret key for full database access
            self._client = create_client(url, secret_key)
            
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise
    
    @property
    def client(self) -> Client:
        """
        Get the Supabase client instance.
        
        Returns:
            Client: Supabase client object
        """
        if self._client is None:
            self._initialize_client()
        return self._client


class BaseRepository:
    """
    Base repository class that provides common database operations.
    All repository implementations should inherit from this class.
    
    Usage:
        class EmployeeRepo(BaseRepository):
            def __init__(self):
                super().__init__('employees')
            
            def get_by_department(self, department: str):
                return self.select().eq('department', department).execute()
    """
    
    def __init__(self, table_name: str):
        """
        Initialize the base repository.
        
        Args:
            table_name: Name of the database table
        """
        self.db = SupabaseConnection()
        self.table_name = table_name
    
    @property
    def table(self):
        """Get the table reference for chaining operations."""
        return self.db.client.table(self.table_name)
    
    def select(self, columns: str = "*"):
        """
        Start a SELECT query.
        
        Args:
            columns: Columns to select (default: "*")
        
        Returns:
            Query builder for chaining
        """
        return self.table.select(columns)
    
    def insert(self, data: Dict[str, Any] | List[Dict[str, Any]]):
        """
        Insert one or more records.
        
        Args:
            data: Dictionary or list of dictionaries to insert
        
        Returns:
            Insert response
        """
        try:
            response = self.table.insert(data).execute()
            logger.info(f"Inserted record(s) into {self.table_name}")
            return response
        except Exception as e:
            logger.error(f"Failed to insert into {self.table_name}: {e}")
            raise
    
    def update(self, data: Dict[str, Any]):
        """
        Start an UPDATE query.
        
        Args:
            data: Dictionary of fields to update
        
        Returns:
            Query builder for chaining (use .eq() to specify conditions)
        """
        return self.table.update(data)
    
    def delete(self):
        """
        Start a DELETE query.
        
        Returns:
            Query builder for chaining (use .eq() to specify conditions)
        """
        return self.table.delete()
    
    def get_by_id(self, id_value: Any, id_column: str = "id"):
        """
        Get a single record by ID.
        
        Args:
            id_value: The ID value to search for
            id_column: Name of the ID column (default: "id")
        
        Returns:
            Single record or None
        """
        try:
            response = self.select().eq(id_column, id_value).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to get record from {self.table_name}: {e}")
            raise
    
    def get_all(self, limit: Optional[int] = None):
        """
        Get all records from the table.
        
        Args:
            limit: Optional limit on number of records
        
        Returns:
            List of records
        """
        try:
            query = self.select()
            if limit:
                query = query.limit(limit)
            response = query.execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to get records from {self.table_name}: {e}")
            raise


# Convenience function to get Supabase client directly
def get_supabase_client() -> Client:
    """
    Get the Supabase client instance.
    
    Returns:
        Supabase client for direct operations
    """
    return SupabaseConnection().client


_pg_pool: asyncpg.Pool | None = None


async def get_postgres_pool() -> asyncpg.Pool:
    global _pg_pool
    if _pg_pool is None:
        try:
            # Create SSL context for Supabase connection
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            logger.info(f"Connecting to Supabase PostgreSQL: {os.environ.get('SUPABASE_DB_URL', 'NOT SET')[:50]}...")
            
            _pg_pool = await asyncpg.create_pool(
                dsn=os.environ["SUPABASE_DB_URL"],
                min_size=2,
                max_size=10,
                command_timeout=10,
                ssl=ssl_context,              # Use SSL context with relaxed verification
                statement_cache_size=0,       # Required for PgBouncer transaction pooler
            )
            logger.info("✅ PostgreSQL pool created successfully")
        except Exception as e:
            logger.error(f"❌ Failed to create PostgreSQL pool: {e}")
            raise
    return _pg_pool


async def close_postgres_pool():
    global _pg_pool
    if _pg_pool:
        await _pg_pool.close()
        _pg_pool = None
