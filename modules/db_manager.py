import sqlite3
import json
from django.db import connection
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class DynamicDBManager:
    """
    Manages dynamic creation and interaction with tables in the database.
    This class handles the dynamic SQL operations needed for the module system.
    """
    
    @staticmethod
    def create_table(table_name, fields):
        """
        Dynamically creates a new table in the database
        
        Args:
            table_name (str): Name of the table to create
            fields (dict): Dictionary with field names as keys and SQL type definitions as values
                           Example: {'id': 'INTEGER PRIMARY KEY', 'name': 'TEXT', 'value': 'REAL'}
        
        Returns:
            bool: True if creation was successful, False otherwise
        """
        # Sanitize table name to prevent SQL injection
        if not table_name.isalnum():
            safe_table_name = ''.join(c for c in table_name if c.isalnum())
            logger.warning(f"Table name contains non-alphanumeric characters. Sanitizing from '{table_name}' to '{safe_table_name}'")
            table_name = safe_table_name
        
        # Convert the field dictionary to SQL column definitions
        columns = []
        for name, data_type in fields.items():
            # Sanitize column names to prevent SQL injection
            if not name.replace('_', '').isalnum():
                safe_name = ''.join(c if c.isalnum() or c == '_' else '' for c in name)
                logger.warning(f"Column name contains invalid characters. Sanitizing from '{name}' to '{safe_name}'")
                name = safe_name
            
            columns.append(f"{name} {data_type}")
        
        # Create the table
        column_definitions = ", ".join(columns)
        create_query = f"CREATE TABLE IF NOT EXISTS {table_name} ({column_definitions})"
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(create_query)
            logger.info(f"Successfully created table '{table_name}'")
            return True
        except Exception as e:
            logger.error(f"Error creating table '{table_name}': {str(e)}")
            return False
    
    @staticmethod
    def drop_table(table_name):
        """
        Drops a table from the database
        
        Args:
            table_name (str): Name of the table to drop
        
        Returns:
            bool: True if successful, False otherwise
        """
        # Sanitize table name
        if not table_name.isalnum():
            safe_table_name = ''.join(c for c in table_name if c.isalnum())
            logger.warning(f"Table name contains non-alphanumeric characters. Sanitizing from '{table_name}' to '{safe_table_name}'")
            table_name = safe_table_name
            
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            logger.info(f"Successfully dropped table '{table_name}'")
            return True
        except Exception as e:
            logger.error(f"Error dropping table '{table_name}': {str(e)}")
            return False
        
    @staticmethod
    def create_table_with_constraints(table_name, fields, constraints=None):
        """
        Dynamically creates a new table in the database with additional constraints
        
        Args:
            table_name (str): Name of the table to create
            fields (dict): Dictionary with field names as keys and SQL type definitions as values
                        Example: {'id': 'INTEGER PRIMARY KEY', 'name': 'TEXT', 'value': 'REAL'}
            constraints (list, optional): List of additional constraints like foreign keys
            
        Returns:
            bool: True if creation was successful, False otherwise
        """
        # Sanitize table name to prevent SQL injection
        if not table_name.isalnum():
            safe_table_name = ''.join(c for c in table_name if c.isalnum())
            logger.warning(f"Table name contains non-alphanumeric characters. Sanitizing from '{table_name}' to '{safe_table_name}'")
            table_name = safe_table_name
        
        # Convert the field dictionary to SQL column definitions
        columns = []
        for name, data_type in fields.items():
            # Sanitize column names to prevent SQL injection
            if not name.replace('_', '').isalnum():
                safe_name = ''.join(c if c.isalnum() or c == '_' else '' for c in name)
                logger.warning(f"Column name contains invalid characters. Sanitizing from '{name}' to '{safe_name}'")
                name = safe_name
            
            columns.append(f"{name} {data_type}")
        
        # Add additional constraints if provided
        if constraints:
            for constraint in constraints:
                columns.append(constraint)
        
        # Create the table
        column_definitions = ", ".join(columns)
        create_query = f"CREATE TABLE IF NOT EXISTS {table_name} ({column_definitions})"
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(create_query)
            logger.info(f"Successfully created table '{table_name}' with constraints")
            return True
        except Exception as e:
            logger.error(f"Error creating table '{table_name}' with constraints: {str(e)}")
            logger.error(f"SQL: {create_query}")
            return False

    @staticmethod
    def insert_data(table_name, data):
        """
        Insert data into a dynamic table
        
        Args:
            table_name (str): Name of the table
            data (dict): Dictionary with column names as keys and values to insert
        
        Returns:
            int: ID of the inserted row or -1 if failed
        """
        # Sanitize table name
        if not table_name.isalnum():
            safe_table_name = ''.join(c for c in table_name if c.isalnum())
            table_name = safe_table_name
        
        # Get the actual table schema to match field names
        actual_columns = []
        with connection.cursor() as cursor:
            try:
                cursor.execute(f"PRAGMA table_info({table_name})")
                actual_columns = [col[1] for col in cursor.fetchall()]
            except Exception as e:
                logger.error(f"Error getting table schema for '{table_name}': {str(e)}")
                return -1
        
        # If no columns found, report error
        if not actual_columns:
            logger.error(f"No columns found for table '{table_name}'")
            return -1
        
        # Map input data to actual columns, excluding fields that don't exist in the table
        valid_data = {}
        for col, val in data.items():
            # Try to find a matching column in the actual schema
            if col in actual_columns:
                valid_data[col] = val
        
        # If no valid data found after mapping, try to use first N fields
        if not valid_data and len(data) <= len(actual_columns):
            # Map the first N fields in order
            sorted_data = sorted(data.items())  # Sort to maintain consistent order
            valid_data = {actual_columns[i]: val for i, (_, val) in enumerate(sorted_data) if i < len(actual_columns)}
        
        # If still no valid data, report error
        if not valid_data:
            logger.error(f"No valid column mapping found for table '{table_name}'")
            logger.error(f"Available columns: {actual_columns}")
            logger.error(f"Provided data keys: {list(data.keys())}")
            return -1
        
        # Prepare the query
        columns = list(valid_data.keys())
        placeholders = ["%s" for _ in columns]  # Using %s for Django's SQLite
        values = list(valid_data.values())
        
        columns_str = ', '.join(columns)
        placeholders_str = ', '.join(placeholders)
        
        query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders_str})"
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, values)
                # Get the ID of the inserted row
                cursor.execute("SELECT last_insert_rowid()")
                row_id = cursor.fetchone()[0]
                logger.info(f"Successfully inserted into '{table_name}' with ID {row_id}")
                return row_id
        except Exception as e:
            logger.error(f"Error inserting into table '{table_name}': {str(e)}")
            logger.error(f"Query: {query}")
            logger.error(f"Values: {values}")
            return -1
    
    @staticmethod
    def query_data(table_name, columns=None, where=None, params=None, limit=None, order_by=None):
        """
        Query data from a dynamic table
        
        Args:
            table_name (str): Name of the table
            columns (list): List of columns to select, None for all
            where (str): WHERE clause, without the WHERE keyword
            params (list): Parameters for WHERE clause
            limit (int): Maximum number of rows to return
            order_by (str): ORDER BY clause, without the ORDER BY keywords
        
        Returns:
            list: List of dictionaries representing rows, empty list if failed
        """
        # Sanitize table name
        if not table_name.isalnum():
            safe_table_name = ''.join(c for c in table_name if c.isalnum())
            table_name = safe_table_name
        
        # Build the query
        if columns is None:
            columns_str = '*'
        else:
            # Sanitize column names
            safe_columns = []
            for col in columns:
                if not col.replace('_', '').isalnum():
                    safe_col = ''.join(c if c.isalnum() or c == '_' else '' for c in col)
                    safe_columns.append(safe_col)
                else:
                    safe_columns.append(col)
            columns_str = ', '.join(safe_columns)
        
        query = f"SELECT {columns_str} FROM {table_name}"
        
        if where:
            query += f" WHERE {where}"
        
        if order_by:
            query += f" ORDER BY {order_by}"
        
        if limit:
            query += f" LIMIT {int(limit)}"
        
        if params is None:
            params = []
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                return [
                    dict(zip(columns, row))
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            logger.error(f"Error querying table '{table_name}': {str(e)}")
            return []
    
    @staticmethod
    def update_data(table_name, data, where, params):
        """
        Update data in a dynamic table
        
        Args:
            table_name (str): Name of the table
            data (dict): Dictionary with column names as keys and new values
            where (str): WHERE clause, without the WHERE keyword
            params (list): Parameters for WHERE clause
        
        Returns:
            int: Number of rows affected or -1 if failed
        """
        # Sanitize table name
        if not table_name.isalnum():
            safe_table_name = ''.join(c for c in table_name if c.isalnum())
            table_name = safe_table_name
        
        set_clauses = []
        set_values = []
        
        for col, val in data.items():
            # Sanitize column names
            if not col.replace('_', '').isalnum():
                safe_col = ''.join(c if c.isalnum() or c == '_' else '' for c in col)
                col = safe_col
            
            set_clauses.append(f"{col} = ?")
            set_values.append(val)
        
        set_str = ', '.join(set_clauses)
        
        query = f"UPDATE {table_name} SET {set_str} WHERE {where}"
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, set_values + params)
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Error updating table '{table_name}': {str(e)}")
            return -1
    
    @staticmethod
    def delete_data(table_name, where, params):
        """
        Delete data from a dynamic table
        
        Args:
            table_name (str): Name of the table
            where (str): WHERE clause, without the WHERE keyword
            params (list): Parameters for WHERE clause
        
        Returns:
            int: Number of rows affected or -1 if failed
        """
        # Sanitize table name
        if not table_name.isalnum():
            safe_table_name = ''.join(c for c in table_name if c.isalnum())
            table_name = safe_table_name
        
        query = f"DELETE FROM {table_name} WHERE {where}"
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Error deleting from table '{table_name}': {str(e)}")
            return -1
    
    @staticmethod
    def add_column(table_name, column_name, data_type):
        """
        Add a new column to an existing table
        
        Args:
            table_name (str): Name of the table
            column_name (str): Name of the new column
            data_type (str): SQL data type for the new column
        
        Returns:
            bool: True if successful, False otherwise
        """
        # Sanitize table and column names
        if not table_name.isalnum():
            safe_table_name = ''.join(c for c in table_name if c.isalnum())
            table_name = safe_table_name
        
        if not column_name.replace('_', '').isalnum():
            safe_column_name = ''.join(c if c.isalnum() or c == '_' else '' for c in column_name)
            column_name = safe_column_name
        
        query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {data_type}"

        
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(query)
            logger.info(f"Successfully added column '{column_name}' to table '{table_name}'")
            return True
        except Exception as e:
            logger.error(f"Error adding column to table '{table_name}': {str(e)}")
            return False
    
    @staticmethod
    def get_table_schema(table_name):
        """
        Get the schema of an existing table
        
        Args:
            table_name (str): Name of the table
        
        Returns:
            list: List of dictionaries with column information
        """
        # Sanitize table name
        if not table_name.isalnum():
            safe_table_name = ''.join(c for c in table_name if c.isalnum())
            table_name = safe_table_name
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = []
                for row in cursor.fetchall():
                    column = {
                        'cid': row[0],          # Column ID
                        'name': row[1],         # Column name
                        'type': row[2],         # Data type
                        'notnull': row[3],      # Not null constraint
                        'default_value': row[4], # Default value
                        'pk': row[5]            # Is primary key
                    }
                    columns.append(column)
                return columns
        except Exception as e:
            logger.error(f"Error getting schema for table '{table_name}': {str(e)}")
            return []
    
    @staticmethod
    def table_exists(table_name):
        """
        Check if a table exists in the database
        
        Args:
            table_name (str): Name of the table
        
        Returns:
            bool: True if the table exists, False otherwise
        """
        # Sanitize table name
        if not table_name.isalnum():
            safe_table_name = ''.join(c for c in table_name if c.isalnum())
            table_name = safe_table_name
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    [table_name]
                )
                return bool(cursor.fetchone())
        except Exception as e:
            logger.error(f"Error checking if table '{table_name}' exists: {str(e)}")
            return False