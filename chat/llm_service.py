import os
import json
import logging
import openai
from django.conf import settings

logger = logging.getLogger(__name__)


class LLMService:
    """
    Service for interacting with Azure OpenAI API
    """
    
    def __init__(self):
        """Initialize the LLM service with Azure OpenAI settings"""
        self.api_key = settings.AZURE_OPENAI_API_KEY
        self.endpoint = settings.AZURE_OPENAI_ENDPOINT
        self.deployment = settings.AZURE_OPENAI_DEPLOYMENT
        self.api_version = settings.AZURE_OPENAI_API_VERSION
        
        # Configure the OpenAI client for Azure
        openai.api_key = self.api_key
        openai.api_base = self.endpoint
        openai.api_type = 'azure'
        openai.api_version = self.api_version
    
    def generate_response(self, messages, system_message=None, max_tokens=1000, temperature=0.7):
        """
        Generate a response from the LLM
        
        Args:
            messages (list): List of message dictionaries with 'role' and 'content'
            system_message (str, optional): System message to prepend
            max_tokens (int): Maximum number of tokens to generate
            temperature (float): Temperature for generation (0-1)
            
        Returns:
            dict: Response from the LLM with content and any parsed actions
        """
        try:
            # Prepend system message if provided
            if system_message:
                full_messages = [{"role": "system", "content": system_message}] + messages
            else:
                full_messages = messages
            
            # Call the Azure OpenAI API
            response = openai.ChatCompletion.create(
                engine=self.deployment,
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                n=1,
                stop=None
            )
            
            # Extract the content from the response
            assistant_message = response.choices[0].message['content']
            
            # Parse the response for any actions
            actions = self._parse_actions(assistant_message)
            
            return {
                "content": assistant_message,
                "actions": actions
            }
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {str(e)}")
            return {
                "content": "I'm sorry, I encountered an error while processing your request.",
                "actions": []
            }
    
    def _parse_actions(self, content):
        """
        Parse the LLM response for any action commands
        
        Args:
            content (str): The LLM response content
            
        Returns:
            list: List of parsed actions
        """
        # Look for action blocks in the format:
        # [ACTION:action_type]
        # action_data_as_json
        # [/ACTION]
        
        actions = []
        import re
        
        # Match action blocks
        action_pattern = r'\[ACTION:(\w+)\](.*?)\[/ACTION\]'
        matches = re.findall(action_pattern, content, re.DOTALL)
        
        for action_type, action_data in matches:
            try:
                # Try to parse as JSON
                data = json.loads(action_data.strip())
                actions.append({
                    "type": action_type,
                    "data": data
                })
            except json.JSONDecodeError:
                # If not valid JSON, use as plain text
                actions.append({
                    "type": action_type,
                    "data": action_data.strip()
                })
        
        return actions

class ModuleAssistant:
    """
    Assistant specifically for handling module operations through LLM
    """
    
    def __init__(self):
        self.llm_service = LLMService()
    
    def analyze_user_request(self, user_message, question_count=0):
        """
        Analyze a user's request to understand what they want to build
        
        Args:
            user_message (str): The user's message describing what they want
            question_count (int): Number of questions already asked
            
        Returns:
            dict: Analysis of the user's request
        """
        # If we've already asked questions or it's a simple request, proceed right away
        if question_count > 0 or len(user_message.split()) < 30:
            return {
                "understanding": "Building module based on user request.",
                "ready_to_proceed": True,
                "clarifying_questions": []
            }
            
        system_message = """
        You are a database designer for a web-based SaaS platform that dynamically creates modules.
        
        IMPORTANT CONTEXT:
        1. You're creating ONLY database tables and web UI components within our existing platform
        2. The UI is ALREADY defined by our platform - it's a web-based interface with forms and tables
        3. We are NOT building standalone applications, command-line tools, or using external frameworks
        4. We are NOT asking implementation questions about frameworks, technology choices, etc.
        5. Your ONLY job is to determine what DATABASE TABLES and FIELDS are needed
        
        NEVER ask about:
        - Implementation details (GUI frameworks, terminal apps, etc.)
        - Technology choices
        - Programming languages
        - Design patterns
        - Deployment options
        
        ONLY ask critical questions about DATABASE requirements if absolutely necessary.
        """
        
        prompt = f"""
        I need to create a module in our dynamic SaaS platform based on this request:
        
        "{user_message}"
        
        Return a JSON response:
        {{
            "understanding": "Brief description of the database tables needed",
            "clarifying_questions": ["ONLY include critical database structure questions if absolutely necessary"],
            "ready_to_proceed": true/false
        }}
        
        REMEMBER: 
        - We're ONLY creating database tables and fields
        - The UI is already handled by our platform
        - DO NOT ask about implementation details, frameworks, or technology choices
        - For simple requests, make reasonable assumptions and set ready_to_proceed to true
        - We're building a web-based system, not a standalone app or terminal program
        """
        
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_service.generate_response(
            messages, 
            system_message=system_message, 
            temperature=0.2
        )
        
        # Extract and parse the analysis from the response
        try:
            # Look for JSON block
            import re
            json_pattern = r'```json\s*(.*?)\s*```|{.*}'
            match = re.search(json_pattern, response["content"], re.DOTALL)
            
            if match:
                json_str = match.group(1) if match.group(1) else match.group(0)
                analysis = json.loads(json_str)
                
                # For simple requests or if we've already asked a question, just proceed
                if len(user_message.split()) < 30 or question_count > 0:
                    analysis['ready_to_proceed'] = True
                    analysis['clarifying_questions'] = []
                
                # Limit to one question if absolutely necessary
                if 'clarifying_questions' in analysis and analysis['clarifying_questions']:
                    analysis['clarifying_questions'] = [analysis['clarifying_questions'][0]]
                    if question_count > 0:  # If we've already asked something, proceed anyway
                        analysis['ready_to_proceed'] = True
                        analysis['clarifying_questions'] = []
                
                return analysis
            else:
                # If parsing fails, return ready to proceed to avoid blocking
                return {
                    "understanding": "Creating database tables based on your request.",
                    "ready_to_proceed": True,
                    "clarifying_questions": []
                }
        except Exception as e:
            logger.error(f"Error parsing analysis from LLM response: {str(e)}")
            # If there's any error, default to proceeding
            return {
                "understanding": "Creating database tables based on your request.",
                "ready_to_proceed": True,
                "clarifying_questions": []
            }
    
    def generate_schema_from_description(self, description, additional_context=None):
        """
        Generate a database schema from a description
        
        Args:
            description (str): Description of the data model
            additional_context (dict, optional): Additional context or clarifications
            
        Returns:
            dict: Generated schema with table and field definitions
        """
        system_message = """
        You are a database designer for a web-based SaaS platform.
        Your task is to create SQLite database tables based on user requirements.
        
        IMPORTANT CONTEXT:
        1. We are ONLY designing database tables, fields, and relationships
        2. The tables will be used in a web application with a standard form-based UI
        3. DO NOT include implementation details or UI-specific fields
        4. Follow SQLite syntax and conventions
        """
        
        context_str = ""
        if additional_context:
            context_str = "\nAdditional context and clarifications:\n" + json.dumps(additional_context, indent=2)
        
        prompt = f"""
        Design SQLite database tables for this module:
        
        {description}{context_str}
        
        Output ONLY a JSON object with this structure:
        {{
            "table_name": {{
                "fields": {{
                    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                    "field_name": "DATA_TYPE [CONSTRAINTS]",
                    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                    "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                }},
                "description": "Purpose of this table"
            }}
        }}
        
        Rules:
        1. Use snake_case for table and field names
        2. Include standard fields (id, created_at, updated_at) for all tables
        3. Use appropriate data types (INTEGER, TEXT, REAL, BOOLEAN, TIMESTAMP)
        4. Add foreign keys with naming pattern: related_table_id
        5. Include NOT NULL constraints where appropriate
        """
        
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_service.generate_response(
            messages, 
            system_message=system_message, 
            temperature=0.2
        )
        
        # Extract and parse the schema from the response
        try:
            # Look for JSON block
            import re
            json_pattern = r'```json\s*(.*?)\s*```|{.*}'
            match = re.search(json_pattern, response["content"], re.DOTALL)
            
            if match:
                json_str = match.group(1) if match.group(1) else match.group(0)
                schema = json.loads(json_str)
                return schema
            else:
                logger.error("No valid JSON schema found in LLM response")
                # Create a simple fallback schema based on the description
                return self._create_fallback_schema(description)
        except Exception as e:
            logger.error(f"Error parsing schema from LLM response: {str(e)}")
            # Return fallback schema on error
            return self._create_fallback_schema(description)
    
    def _create_fallback_schema(self, description):
        """Create a fallback schema based on common words in the description"""
        schema = {}
        
        # Extract potential table names from description
        words = description.lower().replace(',', ' ').replace('.', ' ').split()
        potential_tables = [w for w in words if len(w) > 3 and w not in ['this', 'that', 'with', 'have', 'where', 'what', 'when', 'from', 'their']]
        
        # Use common words as potential table names
        table_counts = {}
        for word in potential_tables:
            if word in table_counts:
                table_counts[word] += 1
            else:
                table_counts[word] = 1
        
        # Get top 2 potential table names
        top_tables = sorted(table_counts.items(), key=lambda x: x[1], reverse=True)[:2]
        
        # If no tables found, create a generic one
        if not top_tables:
            schema["items"] = {
                "fields": {
                    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                    "name": "TEXT NOT NULL",
                    "description": "TEXT",
                    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                    "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                },
                "description": "Main data table for the module"
            }
        else:
            # Create tables based on extracted names
            for table_name, _ in top_tables:
                schema[table_name] = {
                    "fields": {
                        "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                        "name": "TEXT NOT NULL",
                        "description": "TEXT",
                        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                        "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                    },
                    "description": f"Table for {table_name}"
                }
                
            # If we have two tables, add a relationship
            if len(top_tables) >= 2:
                parent_table = top_tables[0][0]
                child_table = top_tables[1][0]
                schema[child_table]["fields"][f"{parent_table}_id"] = "INTEGER"
        
        return schema
    
    def generate_ui_definition(self, module_name, schema, description):
        """
        Generate a UI definition based on module schema and description
        
        Args:
            module_name (str): Name of the module
            schema (dict): Database schema
            description (str): Description of the module
            
        Returns:
            dict: UI definition for the module
        """
        system_message = """
        You are a UI designer for a web-based SaaS platform.
        Your task is to create UI definitions that will be rendered by our platform.
        
        IMPORTANT CONTEXT:
        1. We have a standardized UI system with forms and data display components
        2. You are creating JSON definitions that our system will render into web forms
        3. You need to map database fields to UI components
        4. Each table should have its own add/edit form and data display section
        """
        
        prompt = f"""
        Create a UI definition for a module named "{module_name}" with this database schema:
        
        {json.dumps(schema, indent=2)}
        
        Module description: {description}
        
        Output ONLY a JSON object with this structure:
        {{
            "title": "{module_name}",
            "layout": "standard",
            "sections": [
                {{
                    "title": "Add [Table Name]",
                    "description": "Form to add new records",
                    "type": "form",
                    "target_table": "actual_table_name_from_schema",
                    "components": [
                        {{
                            "type": "text_input",
                            "field": "actual_db_field_name",
                            "label": "User Friendly Label",
                            "placeholder": "Enter value...",
                            "required": true
                        }}
                    ],
                    "actions": [
                        {{
                            "label": "Save",
                            "action": "save",
                            "style": "primary"
                        }}
                    ]
                }},
                {{
                    "title": "View [Table Name]",
                    "type": "display",
                    "target_table": "actual_table_name_from_schema"
                }}
            ]
        }}
        
        Rules:
        1. Create a separate form section for EACH table in the schema
        2. Create a display section for EACH table to view records
        3. Use the ACTUAL database field names in the "field" property of components
        4. Skip id, created_at, and updated_at fields in forms
        5. Add appropriate UI components based on field data types
           - TEXT fields → text_input or textarea
           - INTEGER/REAL fields → number_input
           - BOOLEAN fields → checkbox
           - Foreign key fields → select component
        6. Add filter controls for tables that have relationships
        """
        
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_service.generate_response(
            messages, 
            system_message=system_message, 
            temperature=0.2
        )
        
        # Extract and parse the UI definition from the response
        try:
            # Look for JSON block
            import re
            json_pattern = r'```json\s*(.*?)\s*```|{.*}'
            match = re.search(json_pattern, response["content"], re.DOTALL)
            
            if match:
                json_str = match.group(1) if match.group(1) else match.group(0)
                ui_definition = json.loads(json_str)
                return ui_definition
            else:
                logger.error("No valid JSON UI definition found in LLM response")
                # Return a simple fallback UI
                return self._create_fallback_ui(module_name, schema)
        except Exception as e:
            logger.error(f"Error parsing UI definition from LLM response: {str(e)}")
            # Return fallback UI on error
            return self._create_fallback_ui(module_name, schema)
    
    def _create_fallback_ui(self, module_name, schema):
        """Create a simple fallback UI when generation fails"""
        sections = []
        
        # Create a section for each table
        for table_name, table_data in schema.items():
            form_components = []
            
            # Add components for each field (excluding id and timestamps)
            for field_name, field_type in table_data.get("fields", {}).items():
                if field_name not in ["id", "created_at", "updated_at"]:
                    # Determine field type
                    component_type = "text_input"
                    if "INTEGER" in field_type or "REAL" in field_type:
                        component_type = "number_input"
                    elif "BOOLEAN" in field_type:
                        component_type = "checkbox"
                    
                    # Create component
                    component = {
                        "type": component_type,
                        "field": field_name,
                        "label": field_name.replace("_", " ").title(),
                        "placeholder": f"Enter {field_name.replace('_', ' ')}",
                        "required": "NOT NULL" in field_type
                    }
                    form_components.append(component)
            
            # Add form section
            if form_components:
                form_section = {
                    "title": f"Add {table_name.title()}",
                    "description": f"Add new {table_name} records",
                    "type": "form",
                    "target_table": table_name,
                    "components": form_components,
                    "actions": [
                        {
                            "label": "Save",
                            "action": "save",
                            "style": "primary"
                        }
                    ]
                }
                sections.append(form_section)
            
            # Add display section
            display_section = {
                "title": f"View {table_name.title()}",
                "type": "display",
                "target_table": table_name
            }
            sections.append(display_section)
        
        # Return the complete UI definition
        return {
            "title": module_name,
            "layout": "standard",
            "sections": sections
        }
    
    def parse_user_request(self, user_message, context=None):
        """
        Parse a user request to identify intentions and actions
        
        Args:
            user_message (str): User's message
            context (dict, optional): Additional context
            
        Returns:
            dict: Parsed intentions and actions
        """
        system_message = """
        You are an assistant that helps parse user requests into structured actions.
        Identify what the user wants to do with our SaaS platform.
        """
        
        context_str = ""
        if context:
            context_str = f"\nContext: {json.dumps(context)}"
        
        prompt = f"""
        Parse the following user request into a structured action:{context_str}
        
        User request: "{user_message}"
        
        Output a JSON object with:
        {{
            "intent": "create_module", // or "query_data", "update_record", "create_ui", etc.
            "module_name": "module_name", // if applicable
            "description": "what the user wants", // plain text description
            "parameters": {{
                // any specific parameters extracted from the request
            }}
        }}
        
        Only include fields that are relevant to the detected intent.
        """
        
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_service.generate_response(
            messages, 
            system_message=system_message, 
            temperature=0.2
        )
        
        # Extract and parse the intent from the response
        try:
            # Look for JSON block
            import re
            json_pattern = r'```json\s*(.*?)\s*```|{.*}'
            match = re.search(json_pattern, response["content"], re.DOTALL)
            
            if match:
                json_str = match.group(1) if match.group(1) else match.group(0)
                intent = json.loads(json_str)
                return intent
            else:
                logger.error("No valid JSON intent found in LLM response")
                return {"intent": "unknown"}
        except Exception as e:
            logger.error(f"Error parsing intent from LLM response: {str(e)}")
            return {"intent": "unknown"}

class UIGenerator:
    """
    Service for generating UI components from schema and module definitions
    """
    
    def __init__(self):
        self.llm_service = LLMService()
    
    def generate_ui_definition(self, module_name, schema, module_description):
        """
        Generate a UI definition based on schema and module description
        
        Args:
            module_name (str): Name of the module
            schema (dict): Database schema
            module_description (str): Description of the module
            
        Returns:
            dict: UI definition for the module
        """
        system_message = """
        You are a UI expert who converts database schemas into user interface definitions.
        Create comprehensive, well-structured UI definitions with multiple forms when appropriate.
        Each form should have its own submit button and be designed for a specific task.
        Include data filtering capabilities where relevant (e.g., filter tasks by category).
        Organize the UI logically with separate sections for different functions.
        
        Follow these key principles:
        1. Create separate forms with their own submit buttons for different functions
        2. Add appropriate filter/search capabilities
        3. Include proper form validation requirements
        4. Create logical section groupings
        5. Use descriptive labels and placeholders
        """
        
        prompt = f"""
        Create a detailed UI definition for a module named "{module_name}" with this description:
        
        {module_description}
        
        Database schema:
        {json.dumps(schema, indent=2)}
        
        Your UI definition should follow this structure:
        {{
            "title": "{module_name}",
            "layout": "standard", // or "tabbed", "wizard", etc.
            "sections": [
                {{
                    "title": "Section Title",
                    "description": "Brief description of this section's purpose",
                    "type": "form", // or "display", "filter", etc.
                    "target_table": "table_name", // specify which table this section submits to
                    "components": [
                        {{
                            "type": "text_input", // or "number_input", "select", "checkbox", etc.
                            "field": "actual_db_field_name", // actual database field name
                            "label": "User Friendly Label",
                            "placeholder": "Enter value...",
                            "required": true,
                            "validation": "any validation rules"
                        }},
                        // More components...
                    ],
                    "actions": [
                        {{
                            "label": "Save",
                            "action": "save",
                            "style": "primary"
                        }}
                    ],
                    "filters": [ // Optional filtering components
                        {{
                            "type": "select",
                            "label": "Filter by Category",
                            "options_from": "categories", // Reference to another table
                            "target_field": "category_id" // Field to filter on
                        }}
                    ]
                }},
                // More sections...
            ]
        }}
        
        Ensure you create separate forms with separate submit buttons for different functions.
        Map UI fields directly to actual database field names from the schema.
        Add filter dropdowns where it makes sense to filter related data.
        """
        
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_service.generate_response(
            messages, 
            system_message=system_message, 
            temperature=0.3,
            max_tokens=2000
        )
        
        # Extract and parse the UI definition from the response
        try:
            # Look for JSON block
            import re
            json_pattern = r'```json\s*(.*?)\s*```|{.*}'
            match = re.search(json_pattern, response["content"], re.DOTALL)
            
            if match:
                json_str = match.group(1) if match.group(1) else match.group(0)
                ui_definition = json.loads(json_str)
                return ui_definition
            else:
                logger.error("No valid JSON UI definition found in LLM response")
                return {}
        except Exception as e:
            logger.error(f"Error parsing UI definition from LLM response: {str(e)}")
            return {}
    
    def generate_react_component(self, module_name, ui_definition, schema):
        """
        Generate a React component based on UI definition and schema
        
        Args:
            module_name (str): Name of the module
            ui_definition (dict): UI definition
            schema (dict): Database schema
            
        Returns:
            str: React component code
        """
        system_message = """
        You are a React developer who creates components based on UI and schema definitions.
        Output valid React code that implements the specified UI with multiple forms and filtering capabilities.
        Include proper form submission handling for each separate form.
        Implement filtering functionality where specified.
        """
        
        prompt = f"""
        Create a React component for a module named "{module_name}" with this UI definition and schema:
        
        UI Definition:
        {json.dumps(ui_definition, indent=2)}
        
        Schema:
        {json.dumps(schema, indent=2)}
        
        Generate complete, working React code implementing this UI with these features:
        1. Separate form submission handlers for each form section
        2. Filtering functionality as specified in the UI definition
        3. Form validation
        4. Error handling
        5. Loading states during form submission
        6. Success messages after operations
        
        Use modern React patterns including hooks. Use tailwind CSS for styling.
        Map form fields directly to the actual database field names in the API calls.
        """
        
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_service.generate_response(
            messages, 
            system_message=system_message, 
            temperature=0.3,
            max_tokens=2000
        )
        
        # Extract the React component from the response
        try:
            # Look for code block
            import re
            code_pattern = r'```(?:jsx|tsx|javascript|react)?\s*(.*?)\s*```'
            match = re.search(code_pattern, response["content"], re.DOTALL)
            
            if match:
                code = match.group(1)
                return code
            else:
                # Just return the whole response as it might be code without markdown
                return response["content"]
        except Exception as e:
            logger.error(f"Error extracting React component: {str(e)}")
            return ""