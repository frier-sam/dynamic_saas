"""
Database Diagnostic Tool for Dynamic SaaS Generator

This script helps diagnose issues with dynamic tables and data insertion.
Run this from the Django shell:

python manage.py shell
from db_diagnostic import *
run_diagnostics()
"""

from django.db import connection
import json

def list_tables():
    """List all tables in the database"""
    with connection.cursor() as cursor:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
    
    return [table[0] for table in tables]

def get_table_schema(table_name):
    """Get the schema of a table"""
    with connection.cursor() as cursor:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
    
    return [
        {
            'cid': col[0],
            'name': col[1],
            'type': col[2],
            'notnull': col[3],
            'default_value': col[4],
            'pk': col[5]
        }
        for col in columns
    ]

def get_table_data(table_name, limit=10):
    """Get sample data from a table"""
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
        rows = cursor.fetchall()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
    
    return [dict(zip(columns, row)) for row in rows]

def test_insert(table_name, data):
    """Test inserting data into a table"""
    columns = ", ".join(data.keys())
    placeholders = ", ".join(['%s' for _ in data])
    values = list(data.values())
    
    query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, values)
            cursor.execute("SELECT last_insert_rowid()")
            row_id = cursor.fetchone()[0]
            
            # Rollback to avoid actually inserting test data
            connection.rollback()
            
        return {
            'success': True,
            'row_id': row_id,
            'message': 'Test insert successful (rolled back)'
        }
    except Exception as e:
        connection.rollback()
        return {
            'success': False,
            'error': str(e),
            'query': query,
            'values': values
        }

def sanitize_field_name(name):
    """Sanitize a field name for SQL"""
    return ''.join(c if c.isalnum() or c == '_' else '' for c in name)

def suggest_fixes(table_name, data):
    """Suggest fixes for data insertion issues"""
    schema = get_table_schema(table_name)
    
    suggestions = []
    fixed_data = {}
    
    # Check field name compatibility
    for field_name, value in data.items():
        sanitized_name = sanitize_field_name(field_name)
        if sanitized_name != field_name:
            suggestions.append(f"Field name '{field_name}' contains invalid characters. Using '{sanitized_name}' instead.")
            fixed_data[sanitized_name] = value
        else:
            fixed_data[field_name] = value
    
    # Check if schema contains the fields
    schema_fields = {col['name'] for col in schema}
    for field_name in list(fixed_data.keys()):
        if field_name not in schema_fields:
            suggestions.append(f"Field '{field_name}' doesn't exist in the table schema.")
            
            # Try to find a similarly named field
            for schema_field in schema_fields:
                if field_name.lower() in schema_field.lower() or schema_field.lower() in field_name.lower():
                    suggestions.append(f"  - Did you mean '{schema_field}'?")
    
    # Check for NOT NULL constraints
    for col in schema:
        if col['notnull'] and col['default_value'] is None and col['name'] not in fixed_data:
            suggestions.append(f"Field '{col['name']}' cannot be NULL and has no default value.")
    
    return {
        'suggestions': suggestions,
        'fixed_data': fixed_data
    }

def run_diagnostics():
    """Run all diagnostics"""
    print("=== Database Diagnostic Tool ===")
    
    tables = list_tables()
    print(f"\nFound {len(tables)} tables:")
    for i, table in enumerate(tables, 1):
        print(f"{i}. {table}")
    
    table_idx = input("\nEnter table number to diagnose (or table name): ")
    
    try:
        table_idx = int(table_idx) - 1
        table_name = tables[table_idx]
    except (ValueError, IndexError):
        table_name = table_idx
    
    print(f"\n=== Table: {table_name} ===")
    
    # Get schema
    schema = get_table_schema(table_name)
    print("\nSchema:")
    for col in schema:
        null_status = "NOT NULL" if col['notnull'] else "NULL"
        pk_status = "PRIMARY KEY" if col['pk'] else ""
        default = f"DEFAULT {col['default_value']}" if col['default_value'] is not None else ""
        print(f"  - {col['name']} ({col['type']}) {null_status} {default} {pk_status}")
    
    # Get sample data
    data = get_table_data(table_name, 3)
    if data:
        print("\nSample data:")
        for i, row in enumerate(data, 1):
            print(f"  {i}. {json.dumps(row, default=str)}")
    else:
        print("\nNo data in table")
    
    # Test insert with sample data
    print("\n=== Testing Data Insertion ===")
    test_data = {}
    print("Enter test data (empty line to finish):")
    print("Format: field_name=value")
    
    while True:
        line = input().strip()
        if not line:
            break
        
        try:
            field_name, value = line.split('=', 1)
            test_data[field_name.strip()] = value.strip()
        except ValueError:
            print("Invalid format. Use field_name=value")
    
    if not test_data:
        print("No test data provided. Using default test data...")
        
        # Create default test data based on schema
        for col in schema:
            if col['type'].upper() in ('INTEGER', 'INT'):
                test_data[col['name']] = 1
            elif col['type'].upper() in ('REAL', 'FLOAT', 'DOUBLE'):
                test_data[col['name']] = 1.0
            elif col['type'].upper() in ('TEXT', 'VARCHAR', 'CHAR'):
                test_data[col['name']] = 'test_value'
            elif col['type'].upper() == 'BOOLEAN':
                test_data[col['name']] = 1
            elif col['type'].upper() == 'BLOB':
                continue  # Skip BLOB fields
            else:
                test_data[col['name']] = 'test_value'
    
    print(f"\nTesting with data: {json.dumps(test_data, default=str)}")
    
    # Get suggestions first
    fix_suggestions = suggest_fixes(table_name, test_data)
    
    if fix_suggestions['suggestions']:
        print("\nSuggestions:")
        for suggestion in fix_suggestions['suggestions']:
            print(f"  - {suggestion}")
    
    # Test the insert
    result = test_insert(table_name, test_data)
    
    if result['success']:
        print(f"\nSUCCESS! {result['message']}")
    else:
        print(f"\nERROR: {result['error']}")
        print(f"Query: {result['query']}")
        print(f"Values: {result['values']}")
        
        # Try with fixed data if there were suggestions
        if fix_suggestions['suggestions']:
            print("\nTrying with suggested fixes...")
            fixed_result = test_insert(table_name, fix_suggestions['fixed_data'])
            
            if fixed_result['success']:
                print(f"\nSUCCESS with fixed data! {fixed_result['message']}")
                print("Use these fields in your form submission:")
                for k, v in fix_suggestions['fixed_data'].items():
                    print(f"  {k}: {v}")
            else:
                print(f"\nStill ERROR with fixed data: {fixed_result['error']}")
    
    print("\n=== Diagnostic Complete ===")

if __name__ == "__main__":
    run_diagnostics()