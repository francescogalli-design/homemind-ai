"""
Advanced Memory System with embeddings and long-term storage.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
import sqlite3
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer
import numpy as np

logger = logging.getLogger(__name__)


class MemorySystem:
    """Advanced memory system with vector embeddings and semantic search."""
    
    def __init__(self, settings):
        self.settings = settings
        self.embedding_model = None
        self.vector_db = None
        self.db_path = Path(settings.memory_db_path)
        self.collection = None
        
    async def initialize(self):
        """Initialize the memory system."""
        try:
            # Initialize embedding model
            self.embedding_model = SentenceTransformer(self.settings.embeddings_model)
            logger.info("✅ Embedding model loaded")
            
            # Initialize vector database
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Initialize ChromaDB
            client = chromadb.PersistentClient(path=str(self.db_path.parent))
            self.collection = client.get_or_create_collection(
                name="homemind_memories",
                metadata={"description": "HomeMind memory collection"}
            )
            
            # Initialize SQLite for structured data
            await self._init_sqlite_db()
            
            logger.info("✅ Memory system initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize memory system: {e}")
            raise
    
    async def _init_sqlite_db(self):
        """Initialize SQLite database for structured memory."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                message TEXT NOT NULL,
                response TEXT NOT NULL,
                context TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                sentiment REAL,
                category TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                preference_key TEXT NOT NULL,
                preference_value TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, preference_key)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS routines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                routine_type TEXT NOT NULL,
                pattern TEXT NOT NULL,
                confidence REAL,
                last_seen DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    async def store_interaction(self, user_id: str, message: str, response: str, 
                              context: Optional[Dict] = None, sentiment: Optional[float] = None,
                              category: Optional[str] = None):
        """Store an interaction in memory."""
        try:
            # Store in SQLite
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO interactions (user_id, message, response, context, sentiment, category)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, message, response, json.dumps(context) if context else None, 
                  sentiment, category))
            
            conn.commit()
            conn.close()
            
            # Store in vector database for semantic search
            embedding_text = f"User: {message}\nAssistant: {response}"
            embedding = self.embedding_model.encode(embedding_text)
            
            self.collection.add(
                embeddings=[embedding.tolist()],
                documents=[embedding_text],
                metadatas=[{
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat(),
                    "type": "interaction",
                    "sentiment": sentiment,
                    "category": category
                }],
                ids=[f"interaction_{datetime.now().timestamp()}_{user_id}"]
            )
            
            logger.debug(f"Stored interaction for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error storing interaction: {e}")
    
    async def search_memories(self, query: str, user_id: Optional[str] = None, 
                            limit: int = 5, days_back: int = 30) -> List[str]:
        """Search memories using semantic similarity."""
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode(query)
            
            # Build metadata filter
            where_filter = {"type": "interaction"}
            if user_id:
                where_filter["user_id"] = user_id
            
            # Search in vector database
            results = self.collection.query(
                query_embeddings=[query_embedding.tolist()],
                where=where_filter,
                n_results=limit
            )
            
            # Filter by date if needed
            cutoff_date = datetime.now() - timedelta(days=days_back)
            filtered_results = []
            
            for i, doc in enumerate(results["documents"][0]):
                metadata = results["metadatas"][0][i]
                doc_date = datetime.fromisoformat(metadata["timestamp"])
                
                if doc_date >= cutoff_date:
                    filtered_results.append(doc)
            
            return filtered_results
            
        except Exception as e:
            logger.error(f"Error searching memories: {e}")
            return []
    
    async def get_recent_memories(self, user_id: str, limit: int = 10, 
                                category: Optional[str] = None) -> List[str]:
        """Get recent memories for a user."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            query = '''
                SELECT message, response, timestamp FROM interactions 
                WHERE user_id = ?
            '''
            params = [user_id]
            
            if category:
                query += ' AND category = ?'
                params.append(category)
            
            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            
            memories = []
            for message, response, timestamp in results:
                memories.append(f"[{timestamp}] Q: {message} A: {response}")
            
            return memories
            
        except Exception as e:
            logger.error(f"Error getting recent memories: {e}")
            return []
    
    async def store_preference(self, user_id: str, key: str, value: str):
        """Store user preference."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO user_preferences (user_id, preference_key, preference_value)
                VALUES (?, ?, ?)
            ''', (user_id, key, value))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Stored preference for {user_id}: {key} = {value}")
            
        except Exception as e:
            logger.error(f"Error storing preference: {e}")
    
    async def get_preference(self, user_id: str, key: str) -> Optional[str]:
        """Get user preference."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT preference_value FROM user_preferences 
                WHERE user_id = ? AND preference_key = ?
            ''', (user_id, key))
            
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Error getting preference: {e}")
            return None
    
    async def store_routine(self, user_id: str, routine_type: str, pattern: str, confidence: float):
        """Store detected user routine."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO routines (user_id, routine_type, pattern, confidence, last_seen)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, routine_type, pattern, confidence, datetime.now()))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Stored routine for {user_id}: {routine_type}")
            
        except Exception as e:
            logger.error(f"Error storing routine: {e}")
    
    async def get_routines(self, user_id: str, routine_type: Optional[str] = None) -> List[Dict]:
        """Get user routines."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            query = 'SELECT * FROM routines WHERE user_id = ?'
            params = [user_id]
            
            if routine_type:
                query += ' AND routine_type = ?'
                params.append(routine_type)
            
            query += ' ORDER BY confidence DESC'
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            
            routines = []
            for row in results:
                routines.append({
                    "id": row[0],
                    "user_id": row[1],
                    "routine_type": row[2],
                    "pattern": row[3],
                    "confidence": row[4],
                    "last_seen": row[5],
                    "created_at": row[6]
                })
            
            return routines
            
        except Exception as e:
            logger.error(f"Error getting routines: {e}")
            return []
    
    async def get_interaction_stats(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get interaction statistics for a user."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Total interactions
            cursor.execute('''
                SELECT COUNT(*) FROM interactions 
                WHERE user_id = ? AND timestamp >= ?
            ''', (user_id, cutoff_date))
            total_interactions = cursor.fetchone()[0]
            
            # Average sentiment
            cursor.execute('''
                SELECT AVG(sentiment) FROM interactions 
                WHERE user_id = ? AND timestamp >= ? AND sentiment IS NOT NULL
            ''', (user_id, cutoff_date))
            avg_sentiment = cursor.fetchone()[0] or 0
            
            # Top categories
            cursor.execute('''
                SELECT category, COUNT(*) as count FROM interactions 
                WHERE user_id = ? AND timestamp >= ?
                GROUP BY category ORDER BY count DESC LIMIT 5
            ''', (user_id, cutoff_date))
            top_categories = cursor.fetchall()
            
            conn.close()
            
            return {
                "total_interactions": total_interactions,
                "avg_sentiment": avg_sentiment,
                "top_categories": dict(top_categories)
            }
            
        except Exception as e:
            logger.error(f"Error getting interaction stats: {e}")
            return {}
    
    async def cleanup_old_memories(self):
        """Clean up old memories based on retention policy."""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.settings.memory_retention_days)
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Delete old interactions
            cursor.execute('''
                DELETE FROM interactions WHERE timestamp < ?
            ''', (cutoff_date,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            # Clean up vector database (remove old documents)
            # This would require implementing a cleanup mechanism in ChromaDB
            # For now, we'll log the action
            logger.info(f"Cleaned up {deleted_count} old interactions")
            
        except Exception as e:
            logger.error(f"Error cleaning up old memories: {e}")
    
    async def cleanup(self):
        """Cleanup resources."""
        try:
            # Close database connections
            if hasattr(self, 'db_path'):
                pass  # SQLite connections are closed per operation
            
            # Cleanup vector database
            if self.collection:
                pass  # ChromaDB handles cleanup automatically
            
            logger.info("✅ Memory system cleanup complete")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
