"""
Unit tests for database tools.
"""
import pytest
from unittest.mock import Mock, patch
from src.agents.database.tools import search_database, _validate_sql_query, _format_query_result


class TestDatabaseTools:
    """Test cases for database tools."""
    
    def test_validate_sql_query_safe(self):
        """Test that safe SQL queries pass validation."""
        safe_queries = [
            "SELECT * FROM users LIMIT 10",
            "SELECT COUNT(*) FROM transactions",
            "SELECT name, price FROM crypto_prices WHERE date > '2024-01-01'"
        ]
        
        for query in safe_queries:
            assert _validate_sql_query(query) is True
    
    def test_validate_sql_query_dangerous(self):
        """Test that dangerous SQL queries are rejected."""
        dangerous_queries = [
            "DROP TABLE users",
            "DELETE FROM transactions",
            "INSERT INTO users VALUES (1, 'test')",
            "UPDATE users SET name = 'test'",
            "ALTER TABLE users ADD COLUMN test"
        ]
        
        for query in dangerous_queries:
            assert _validate_sql_query(query) is False
    
    def test_format_query_result_empty(self):
        """Test formatting of empty results."""
        result = _format_query_result("")
        assert result == "No data found."
    
    def test_format_query_result_simple(self):
        """Test formatting of simple results."""
        result = _format_query_result("name,price\nbitcoin,50000")
        assert "bitcoin" in result
    
    def test_format_query_result_large(self):
        """Test formatting of large results."""
        large_result = "name,price\n" + "\n".join([f"coin{i},{i*1000}" for i in range(20)])
        formatted = _format_query_result(large_result)
        assert "Query returned 21 rows" in formatted
    
    @patch('src.agents.database.tools._db')
    @patch('src.agents.database.tools._sql_chain')
    def test_search_database_success(self, mock_chain, mock_db):
        """Test successful database search."""
        # Mock the chain to return a safe SQL query
        mock_chain.invoke.return_value = "SELECT * FROM crypto_prices LIMIT 5"
        
        # Mock the database to return results
        mock_db.get_table_info.return_value = "CREATE TABLE crypto_prices (name String, price Float64)"
        mock_db.run.return_value = "bitcoin,50000\nethereum,3000"
        
        result = search_database("Show me the top 5 cryptocurrencies")
        
        assert "bitcoin" in result
        assert "ethereum" in result
    
    @patch('src.agents.database.tools._db')
    @patch('src.agents.database.tools._sql_chain')
    def test_search_database_error_response(self, mock_chain, mock_db):
        """Test database search with LLM error response."""
        # Mock the chain to return an error
        mock_chain.invoke.return_value = "ERROR: Cannot answer this question with available data"
        
        result = search_database("What is the meaning of life?")
        
        assert result == "ERROR: Cannot answer this question with available data"
    
    @patch('src.agents.database.tools._db')
    @patch('src.agents.database.tools._sql_chain')
    def test_search_database_dangerous_query(self, mock_chain, mock_db):
        """Test database search with dangerous SQL generation."""
        # Mock the chain to return a dangerous query
        mock_chain.invoke.return_value = "DROP TABLE users"
        
        result = search_database("Delete all users")
        
        assert "Error: Generated SQL query contains potentially dangerous operations" in result 