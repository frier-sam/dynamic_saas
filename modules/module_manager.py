import json
import logging
from django.contrib.auth.models import User
from django.db import transaction
from .models import Module, DynamicTable, ModuleState
from .db_manager import DynamicDBManager

logger = logging.getLogger(__name__)


class ModuleManager:
    """
    Manages dynamic modules in the system, handling their creation,
    updating, and interaction with the database.
    """
    
    @staticmethod
    def create_module(user, name, description=None, module_type='custom', schema=None, has_gui=False, ui_definition=None):
        """
        Creates a new module for a user
        
        Args:
            user (User): The user who owns the module
            name (str): Name of the module
            description (str, optional): Description of the module
            module_type (str): Type of the module (from Module.MODULE_TYPES)
            schema (dict, optional): Schema definition for the module
            has_gui (bool): Whether the module has a GUI interface
            ui_definition (dict, optional): UI definition for the module
            
        Returns:
            Module: The created module or None if failed
        """
        try:
            with transaction.atomic():
                # Create the module
                module = Module(
                    user=user,
                    name=name,
                    description=description,
                    module_type=module_type,
                    has_gui=has_gui
                )
                
                # Set the schema if provided
                if schema:
                    module.set_schema(schema)
                
                # Set the UI definition if provided
                if ui_definition:
                    module.set_ui_definition(ui_definition)
                
                module.save()
                
                # Create a default state for the module
                ModuleState.objects.create(module=module)
                
                logger.info(f"Created module '{name}' for user '{user.username}'")
                return module
                
        except Exception as e:
            logger.error(f"Error creating module '{name}' for user '{user.username}': {str(e)}")
            return None
        
    
    
    @staticmethod
    def create_table_for_module(module, table_name, fields, description=None):
        """
        Creates a new dynamic table for a module
        
        Args:
            module (Module): The module to create the table for
            table_name (str): Name of the table
            fields (dict): Dictionary mapping field names to SQL types
            description (str, optional): Description of the table
            
        Returns:
            DynamicTable: The created table metadata or None if failed
        """
        try:
            with transaction.atomic():
                # Create the physical table in the database
                # Add a prefix to avoid collisions with Django tables
                physical_table_name = f"module_{module.id}_{table_name}"
                
                # Process fields to properly handle foreign keys
                processed_fields = {}
                foreign_keys = []
                
                for field_name, field_type in fields.items():
                    processed_fields[field_name] = field_type
                    
                    # Check if this is a foreign key field
                    if field_name.endswith('_id'):
                        referenced_table_logical = field_name[:-3]  # Remove '_id'
                        
                        # Try to find the referenced table
                        try:
                            referenced_table = DynamicTable.objects.get(
                                module=module, 
                                name=referenced_table_logical
                            )
                            
                            # Get the physical table name for the referenced table
                            referenced_schema = referenced_table.get_schema()
                            referenced_physical_table = referenced_schema['physical_name']
                            
                            # Define the foreign key constraint
                            foreign_key_def = f"FOREIGN KEY ({field_name}) REFERENCES {referenced_physical_table}(id)"
                            foreign_keys.append(foreign_key_def)
                        except DynamicTable.DoesNotExist:
                            # The referenced table doesn't exist yet
                            # We'll create this as a normal field without a constraint
                            logger.warning(
                                f"Referenced table '{referenced_table_logical}' not found " +
                                f"for foreign key '{field_name}' in table '{table_name}'"
                            )
                
                # Create the table with foreign key constraints
                # Build the SQL including foreign key constraints
                success = DynamicDBManager.create_table_with_constraints(
                    physical_table_name, 
                    processed_fields,
                    foreign_keys
                )
                
                if not success:
                    return None
                
                # Create the table metadata
                table = DynamicTable(
                    module=module,
                    name=table_name,
                    description=description
                )
                
                # Store the schema
                table_schema = {
                    'physical_name': physical_table_name,
                    'fields': fields,
                    'foreign_keys': [{
                        'field': fk.split('(')[1].split(')')[0],
                        'references': fk.split('REFERENCES ')[1].split('(')[0]
                    } for fk in foreign_keys]
                }
                table.set_schema(table_schema)
                table.save()
                
                logger.info(f"Created table '{table_name}' for module '{module.name}'")
                return table
                    
        except Exception as e:
            logger.error(f"Error creating table '{table_name}' for module '{module.name}': {str(e)}")
            return None
    
    @staticmethod
    def get_module(user, module_id=None, module_name=None):
        """
        Get a module by ID or name for a specific user
        
        Args:
            user (User): The user who owns the module
            module_id (int, optional): ID of the module
            module_name (str, optional): Name of the module
            
        Returns:
            Module: The requested module or None if not found
        """
        try:
            if module_id:
                return Module.objects.get(id=module_id, user=user)
            elif module_name:
                return Module.objects.get(name=module_name, user=user)
            else:
                logger.error("Either module_id or module_name must be provided")
                return None
        except Module.DoesNotExist:
            logger.warning(f"Module not found for user '{user.username}'")
            return None
        except Exception as e:
            logger.error(f"Error retrieving module for user '{user.username}': {str(e)}")
            return None
    
    @staticmethod
    def get_user_modules(user):
        """
        Get all modules for a specific user
        
        Args:
            user (User): The user
            
        Returns:
            QuerySet: All modules for the user
        """
        return Module.objects.filter(user=user).order_by('-updated_at')
    
    @staticmethod
    def update_module_ui(module, ui_definition):
        """
        Update the UI definition of a module
        
        Args:
            module (Module): The module to update
            ui_definition (dict): New UI definition
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            module.set_ui_definition(ui_definition)
            module.has_gui = True
            module.save()
            logger.info(f"Updated UI for module '{module.name}'")
            return True
        except Exception as e:
            logger.error(f"Error updating UI for module '{module.name}': {str(e)}")
            return False
    
    @staticmethod
    def insert_data(module, table_name, data):
        """
        Insert data into a module's table
        
        Args:
            module (Module): The module
            table_name (str): Name of the table
            data (dict): Data to insert (column name -> value)
            
        Returns:
            int: ID of the inserted row or -1 if failed
        """
        try:
            # Find the table
            table = DynamicTable.objects.get(module=module, name=table_name)
            schema = table.get_schema()
            physical_table_name = schema['physical_name']
            
            # Process the data to handle foreign keys
            processed_data = {}
            for key, value in data.items():
                processed_data[key] = value
                
                # If this is a foreign key (ends with _id), we need to ensure the
                # referenced table exists and the value is valid
                if key.endswith('_id') and value:
                    # Get the referenced table name (logical)
                    referenced_table_logical = key[:-3]  # Remove '_id'
                    
                    # Try to find the referenced table in this module
                    try:
                        referenced_table = DynamicTable.objects.get(
                            module=module, 
                            name=referenced_table_logical
                        )
                        
                        # We found the referenced table - no need to modify the value
                        # The database constraint should have the correct physical table name
                        pass
                    except DynamicTable.DoesNotExist:
                        # If we can't find the referenced table, log a warning
                        logger.warning(
                            f"Referenced table '{referenced_table_logical}' not found " +
                            f"for foreign key '{key}' in table '{table_name}'"
                        )
            
            # Insert the processed data
            return DynamicDBManager.insert_data(physical_table_name, processed_data)
        except DynamicTable.DoesNotExist:
            logger.warning(f"Table '{table_name}' not found for module '{module.name}'")
            return -1
        except Exception as e:
            logger.error(f"Error inserting data into table '{table_name}': {str(e)}")
            return -1
    
    @staticmethod
    def query_data(module, table_name, columns=None, where=None, params=None, limit=None, order_by=None):
        """
        Query data from a module's table
        
        Args:
            module (Module): The module
            table_name (str): Name of the table
            columns (list, optional): List of columns to select
            where (str, optional): WHERE clause
            params (list, optional): Parameters for WHERE clause
            limit (int, optional): Maximum number of rows to return
            order_by (str, optional): ORDER BY clause
            
        Returns:
            list: List of rows as dictionaries
        """
        try:
            # Find the table
            table = DynamicTable.objects.get(module=module, name=table_name)
            schema = table.get_schema()
            physical_table_name = schema['physical_name']
            
            # Query the data
            return DynamicDBManager.query_data(
                physical_table_name, columns, where, params, limit, order_by
            )
        except DynamicTable.DoesNotExist:
            logger.warning(f"Table '{table_name}' not found for module '{module.name}'")
            return []
        except Exception as e:
            logger.error(f"Error querying data from table '{table_name}': {str(e)}")
            return []
    
    @staticmethod
    def update_data(module, table_name, data, where, params):
        """
        Update data in a module's table
        
        Args:
            module (Module): The module
            table_name (str): Name of the table
            data (dict): Data to update (column name -> value)
            where (str): WHERE clause
            params (list): Parameters for WHERE clause
            
        Returns:
            int: Number of rows affected or -1 if failed
        """
        try:
            # Find the table
            table = DynamicTable.objects.get(module=module, name=table_name)
            schema = table.get_schema()
            physical_table_name = schema['physical_name']
            
            # Update the data
            return DynamicDBManager.update_data(
                physical_table_name, data, where, params
            )
        except DynamicTable.DoesNotExist:
            logger.warning(f"Table '{table_name}' not found for module '{module.name}'")
            return -1
        except Exception as e:
            logger.error(f"Error updating data in table '{table_name}': {str(e)}")
            return -1
    
    @staticmethod
    def delete_module(module):
        """
        Delete a module and all its associated tables
        
        Args:
            module (Module): The module to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with transaction.atomic():
                # Delete all associated tables
                tables = DynamicTable.objects.filter(module=module)
                for table in tables:
                    schema = table.get_schema()
                    physical_table_name = schema['physical_name']
                    DynamicDBManager.drop_table(physical_table_name)
                
                # Delete the module
                module.delete()
                
                logger.info(f"Deleted module '{module.name}'")
                return True
        except Exception as e:
            logger.error(f"Error deleting module '{module.name}': {str(e)}")
            return False
    
    @staticmethod
    def record_module_usage(module):
        """
        Record that a module was used
        
        Args:
            module (Module): The module
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            module.state.increment_usage()
            logger.info(f"Recorded usage for module '{module.name}'")
            return True
        except Exception as e:
            logger.error(f"Error recording usage for module '{module.name}': {str(e)}")
            return False