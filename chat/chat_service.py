import json
import logging
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Conversation, Message
from .llm_service import LLMService, ModuleAssistant, UIGenerator
from modules.module_manager import ModuleManager

logger = logging.getLogger(__name__)


class ChatService:
    """
    Service for managing conversations and handling message processing
    """
    
    def __init__(self):
        self.llm_service = LLMService()
        self.module_assistant = ModuleAssistant()
        self.ui_generator = UIGenerator()
    
    def create_conversation(self, user, title=None, module=None):
        """
        Create a new conversation
        
        Args:
            user (User): The user
            title (str, optional): Title for the conversation
            module (Module, optional): Associated module
            
        Returns:
            Conversation: The created conversation
        """
        # Generate a default title if none provided
        if not title:
            title = f"New Conversation {timezone.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Create the conversation
        conversation = Conversation.objects.create(
            user=user,
            title=title,
            module=module
        )
        
        # Add a system message
        if module:
            content = f"This conversation is specifically about the '{module.name}' module."
        else:
            content = "Welcome! I can help you create and manage custom applications. What would you like to build today?"
        
        Message.objects.create(
            conversation=conversation,
            message_type='system',
            content=content
        )
        
        return conversation
    
    def add_user_message(self, conversation, content):
        """
        Add a user message to a conversation
        
        Args:
            conversation (Conversation): The conversation
            content (str): Message content
            
        Returns:
            Message: The created message
        """
        return Message.objects.create(
            conversation=conversation,
            message_type='user',
            content=content
        )
    
    def add_assistant_message(self, conversation, content, actions=None):
        """
        Add an assistant message to a conversation
        
        Args:
            conversation (Conversation): The conversation
            content (str): Message content
            actions (list, optional): List of actions
            
        Returns:
            Message: The created message
        """
        message = Message.objects.create(
            conversation=conversation,
            message_type='assistant',
            content=content
        )
        
        if actions:
            message.set_actions(actions)
        
        return message
    
    def process_message(self, conversation, user_message_content):
        """
        Process a user message and generate a response
        
        Args:
            conversation (Conversation): The conversation
            user_message_content (str): User message content
            
        Returns:
            dict: Response with message and any performed actions
        """
        # Add the user message to the conversation
        user_message = self.add_user_message(conversation, user_message_content)
        
        # Get context
        context = conversation.get_context()
        
        # Check if we have a pending module creation
        if 'pending_module_creation' in context:
            # This is a response to a clarification question
            pending_module = context['pending_module_creation']
            
            # Update the module description with the new information
            updated_description = pending_module['description'] + "\n\nAdditional information: " + user_message_content
            
            # Create a new intent with the updated information
            intent = {
                'intent': 'create_module',
                'module_name': pending_module['module_name'],
                'description': updated_description,
                'parameters': {
                    'module_type': pending_module['module_type']
                }
            }
            
            # Process the updated intent
            return self._handle_intent_with_response(conversation, intent)
        
        # Check if we have a pending UI creation
        elif 'pending_ui_creation' in context:
            # This is a response to a UI clarification question
            pending_ui = context['pending_ui_creation']
            
            # Update with the new information
            updated_description = pending_ui.get('description', '') + "\n\nAdditional UI preferences: " + user_message_content
            
            # Create a new intent with the updated information
            intent = {
                'intent': 'create_ui',
                'module_name': pending_ui.get('module_name'),
                'description': updated_description
            }
            
            # Process the updated intent
            return self._handle_intent_with_response(conversation, intent)
        
        # Normal flow - parse the user request to identify the intent
        else:
            intent = self.module_assistant.parse_user_request(user_message_content, context)
            return self._handle_intent_with_response(conversation, intent)

    def _handle_intent_with_response(self, conversation, intent):
        """
        Handle an intent and generate a response
        
        Args:
            conversation (Conversation): The conversation
            intent (dict): Parsed intent
            
        Returns:
            dict: Response with message and actions
        """
        # Process the intent
        response_content = None
        actions = []
        
        if intent.get('intent') == 'create_module':
            # Handle module creation intent
            response_data = self._handle_create_module(conversation, intent)
            response_content = response_data.get('content')
            actions = response_data.get('actions', [])
            
        elif intent.get('intent') == 'create_ui':
            # Handle UI creation intent
            response_data = self._handle_create_ui(conversation, intent)
            response_content = response_data.get('content')
            actions = response_data.get('actions', [])
            
        elif intent.get('intent') == 'query_data':
            # Handle data query intent
            response_data = self._handle_query_data(conversation, intent)
            response_content = response_data.get('content')
            actions = response_data.get('actions', [])
            
        elif intent.get('intent') == 'insert_data':
            # Handle data insertion intent
            response_data = self._handle_insert_data(conversation, intent)
            response_content = response_data.get('content')
            actions = response_data.get('actions', [])
            
        else:
            # For other intents, generate a general response
            # Get conversation history
            messages = self._get_conversation_messages(conversation)
            
            # Prepare system message
            if conversation.module:
                system_message = f"""
                You are a helpful assistant specializing in the '{conversation.module.name}' module.
                Help the user interact with this module, providing guidance and executing their requests.
                
                Module description: {conversation.module.description or 'No description available.'}
                
                Be concise and direct. Focus on helping the user accomplish their goals.
                """
            else:
                system_message = """
                You are a helpful assistant that helps users build and interact with custom applications.
                You can create new modules, build UI interfaces, and manage data based on user needs.
                
                Be concise and direct. Make reasonable assumptions rather than asking too many questions.
                Focus on what the user is explicitly asking for.
                """
            
            # Generate response
            llm_response = self.llm_service.generate_response(
                messages, 
                system_message=system_message,
                max_tokens=1000
            )
            
            response_content = llm_response.get('content')
            actions = llm_response.get('actions', [])
        
        # Add the assistant message to the conversation
        assistant_message = self.add_assistant_message(conversation, response_content, actions)
        
        # Update conversation timestamp
        conversation.updated_at = timezone.now()
        conversation.save()
        
        return {
            'message': assistant_message,
            'actions': actions,
            'intent': intent.get('intent')
        }
    
    def _build_message_context(self, conversation):
        """
        Build the context for a message
        
        Args:
            conversation (Conversation): The conversation
            
        Returns:
            dict: Context data
        """
        context = conversation.get_context()
        
        # Add module information if applicable
        if conversation.module:
            module = conversation.module
            
            # Basic module info
            module_info = {
                'id': module.id,
                'name': module.name,
                'description': module.description,
                'type': module.module_type,
                'has_gui': module.has_gui,
                'created_at': module.created_at.isoformat(),
                'updated_at': module.updated_at.isoformat()
            }
            
            # Add schema information
            module_info['schema'] = module.get_schema()
            
            # Add UI information if available
            if module.has_gui:
                module_info['ui_definition'] = module.get_ui_definition()
            
            context['module'] = module_info
            
            # Get available tables
            tables = module.tables.all()
            tables_info = []
            
            for table in tables:
                table_info = {
                    'id': table.id,
                    'name': table.name,
                    'description': table.description,
                    'schema': table.get_schema(),
                    'created_at': table.created_at.isoformat(),
                    'updated_at': table.updated_at.isoformat()
                }
                tables_info.append(table_info)
            
            context['tables'] = tables_info
        
        # Add user information
        user = conversation.user
        context['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email
        }
        
        return context
    
    def _get_conversation_messages(self, conversation, limit=10):
        """
        Get the latest messages from a conversation in the format expected by the LLM
        
        Args:
            conversation (Conversation): The conversation
            limit (int): Maximum number of messages to return
            
        Returns:
            list: Messages in LLM format
        """
        # Get the latest messages
        messages = conversation.messages.order_by('created_at')
        
        # Exclude system messages and limit the number
        user_assistant_messages = [m for m in messages if m.message_type != 'system'][-limit:]
        
        # Convert to the format expected by the LLM
        formatted_messages = []
        for message in user_assistant_messages:
            role = "user" if message.message_type == "user" else "assistant"
            formatted_messages.append({
                "role": role,
                "content": message.content
            })
        
        return formatted_messages
    
    def _handle_create_module(self, conversation, intent):
        """
        Handle the intent to create a new module
        
        Args:
            conversation (Conversation): The conversation
            intent (dict): Parsed intent
            
        Returns:
            dict: Response data
        """
        try:
            # Extract the module details from the intent
            module_name = intent.get('module_name', 'New Module')
            description = intent.get('description', '')
            module_type = intent.get('parameters', {}).get('module_type', 'custom')
            
            # Get question count from context if available
            context = conversation.get_context()
            question_count = context.get('module_question_count', 0)
            
            # First, analyze the user's request
            analysis = self.module_assistant.analyze_user_request(description, question_count)
            
            # If we need clarification and haven't exceeded question limit
            if not analysis.get('ready_to_proceed', False) and question_count < 3 and analysis.get('clarifying_questions'):
                # Increment question count
                context['module_question_count'] = question_count + 1
                
                # Format understanding and questions
                understanding = analysis.get('understanding', '')
                questions = analysis.get('clarifying_questions', [])[:1]  # Just ask one question at a time
                
                questions_text = "\n".join([f"- {q}" for q in questions])
                
                response_content = f"""
                I understand you want to create a module for {module_name}. Here's what I understand so far:
                
                {understanding}
                
                Before I create this module, I have a quick question:
                
                {questions_text}
                
                Once I have this information, I'll create the module for you.
                """
                
                # Store the pending module info
                context['pending_module_creation'] = {
                    'module_name': module_name,
                    'description': description,
                    'module_type': module_type,
                    'analysis': analysis
                }
                conversation.set_context(context)
                
                return {
                    "content": response_content,
                    "actions": []
                }
            
            # Generate schema from description
            schema = self.module_assistant.generate_schema_from_description(description)
            
            # Create the module
            module = ModuleManager.create_module(
                user=conversation.user,
                name=module_name,
                description=description,
                module_type=module_type,
                schema=schema
            )
            
            if not module:
                return {
                    "content": "I'm sorry, I couldn't create the module. Please try again with more details.",
                    "actions": []
                }
            
            # Create tables based on the schema
            tables_created = []
            for table_name, table_data in schema.items():
                if 'fields' in table_data:
                    table = ModuleManager.create_table_for_module(
                        module=module,
                        table_name=table_name,
                        fields=table_data['fields'],
                        description=table_data.get('description', f"Table for {table_name}")
                    )
                    
                    if table:
                        tables_created.append(table_name)
            
            # Update the conversation to link to this module
            conversation.module = module
            conversation.save()
            
            # Reset question count
            context = conversation.get_context()
            if 'module_question_count' in context:
                del context['module_question_count']
            if 'pending_module_creation' in context:
                del context['pending_module_creation']
            conversation.set_context(context)
            
            # Automatically generate UI if there are tables created
            if tables_created:
                ui_definition = self.module_assistant.generate_ui_definition(
                    module_name=module.name,
                    schema=schema,
                    description=description
                )
                
                ModuleManager.update_module_ui(module, ui_definition)
            
            # Schema description for the response
            schema_description = ""
            for table_name, table_data in schema.items():
                if 'fields' in table_data:
                    schema_description += f"\n### {table_name.title()}\n"
                    schema_description += f"{table_data.get('description', '')}\n"
                    
                    # Add fields if there aren't too many
                    field_count = len(table_data['fields'])
                    if field_count <= 10:
                        schema_description += "| Field | Type |\n"
                        schema_description += "|-------|------|\n"
                        
                        for field_name, field_type in table_data['fields'].items():
                            if field_name not in ["id", "created_at", "updated_at"]:
                                schema_description += f"| {field_name} | {field_type} |\n"
                    else:
                        schema_description += f"Contains {field_count} fields including "
                        sample_fields = [f for f in table_data['fields'].keys() if f not in ["id", "created_at", "updated_at"]][:5]
                        schema_description += ", ".join(sample_fields) + " and others.\n"
            
            # Generate a response
            response_content = f"""
            I've created the **{module_name}** module with the following database structure:
            
            {schema_description}
            
            I've also automatically generated a web UI for this module. You can now:
            
            1. **View and interact with your module** by clicking the "View UI" button
            2. **Add data** using the forms provided in the interface
            3. **View and manage your data** in the data tables
            
            The interface is ready to use - no further configuration needed!
            """
            
            return {
                "content": response_content,
                "actions": [
                    {
                        "type": "module_created",
                        "data": {
                            "module_id": module.id,
                            "module_name": module.name,
                            "tables_created": tables_created,
                            "ui_created": True
                        }
                    }
                ]
            }
            
        except Exception as e:
            logger.error(f"Error handling create_module intent: {str(e)}")
            return {
                "content": "I encountered an error while trying to create the module. Please try again with more specific details.",
                "actions": []
            }

    
    def _handle_create_ui(self, conversation, intent):
        """
        Handle the intent to create a UI for a module
        
        Args:
            conversation (Conversation): The conversation
            intent (dict): Parsed intent
            
        Returns:
            dict: Response data
        """
        try:
            # Get the module
            module = conversation.module
            
            if not module:
                module_name = intent.get('module_name')
                if module_name:
                    module = ModuleManager.get_module(
                        user=conversation.user,
                        module_name=module_name
                    )
            
            if not module:
                return {
                    "content": "I couldn't find the module you're referring to. Which module would you like to create a UI for?",
                    "actions": []
                }
            
            # Generate UI definition based on the module's schema and description
            schema = module.get_schema()
            ui_definition = self.module_assistant.generate_ui_definition(
                module_name=module.name,
                schema=schema,
                description=module.description
            )
            
            # Update the module with the UI definition
            success = ModuleManager.update_module_ui(module, ui_definition)
            
            if not success:
                return {
                    "content": "I'm sorry, I couldn't create the UI for this module. Please try again.",
                    "actions": []
                }
            
            # Generate a response
            response_content = f"""
            I've created a web-based user interface for the **{module.name}** module. The UI includes:

            1. **Forms for adding data** to each of your tables
            2. **Data views** to see and manage your records
            3. **Filter capabilities** where appropriate

            You can now click the "View UI" button to interact with your module through the interface.
            """
            
            return {
                "content": response_content,
                "actions": [
                    {
                        "type": "ui_created",
                        "data": {
                            "module_id": module.id,
                            "module_name": module.name
                        }
                    }
                ]
            }
            
        except Exception as e:
            logger.error(f"Error handling create_ui intent: {str(e)}")
            return {
                "content": "I encountered an error while trying to create the UI. Please try again.",
                "actions": []
            }
    
    def _handle_query_data(self, conversation, intent):
        """
        Handle the intent to query data from a module
        
        Args:
            conversation (Conversation): The conversation
            intent (dict): Parsed intent
            
        Returns:
            dict: Response data
        """
        try:
            # Get the module
            module = conversation.module
            
            if not module:
                module_name = intent.get('module_name')
                if module_name:
                    module = ModuleManager.get_module(
                        user=conversation.user,
                        module_name=module_name
                    )
            
            if not module:
                return {
                    "content": "I couldn't find the module you're referring to. Which module's data would you like to query?",
                    "actions": []
                }
            
            # Get query parameters
            params = intent.get('parameters', {})
            table_name = params.get('table_name')
            
            if not table_name:
                # Try to get the table name from the module's tables
                tables = module.tables.all()
                if tables.exists():
                    table_name = tables.first().name
                else:
                    return {
                        "content": "This module doesn't have any tables yet. Would you like to create one?",
                        "actions": []
                    }
            
            # Query the data
            where_clause = params.get('where')
            where_params = params.get('where_params', [])
            limit = params.get('limit')
            order_by = params.get('order_by')
            
            results = ModuleManager.query_data(
                module=module,
                table_name=table_name,
                where=where_clause,
                params=where_params,
                limit=limit,
                order_by=order_by
            )
            
            # Generate a response
            if results:
                # Format the results for display
                result_str = json.dumps(results, indent=2)
                
                response_content = f"""
                Here are the results from the "{table_name}" table:
                
                ```json
                {result_str}
                ```
                
                Is there anything specific you'd like to know about this data?
                """
            else:
                response_content = f"""
                I didn't find any data in the "{table_name}" table matching your query.
                
                Would you like to add some data to this table?
                """
            
            return {
                "content": response_content,
                "actions": [
                    {
                        "type": "query_results",
                        "data": {
                            "table_name": table_name,
                            "results": results
                        }
                    }
                ]
            }
            
        except Exception as e:
            logger.error(f"Error handling query_data intent: {str(e)}")
            return {
                "content": "I encountered an error while trying to query the data. Please try again with more specific details.",
                "actions": []
            }
    
    def _handle_insert_data(self, conversation, intent):
        """
        Handle the intent to insert data into a module
        
        Args:
            conversation (Conversation): The conversation
            intent (dict): Parsed intent
            
        Returns:
            dict: Response data
        """
        try:
            # Get the module
            module = conversation.module
            
            if not module:
                module_name = intent.get('module_name')
                if module_name:
                    module = ModuleManager.get_module(
                        user=conversation.user,
                        module_name=module_name
                    )
            
            if not module:
                return {
                    "content": "I couldn't find the module you're referring to. Which module would you like to add data to?",
                    "actions": []
                }
            
            # Get data parameters
            params = intent.get('parameters', {})
            table_name = params.get('table_name')
            data = params.get('data', {})
            
            if not table_name:
                # Try to get the table name from the module's tables
                tables = module.tables.all()
                if tables.exists():
                    table_name = tables.first().name
                else:
                    return {
                        "content": "This module doesn't have any tables yet. Would you like to create one?",
                        "actions": []
                    }
            
            if not data:
                return {
                    "content": "What data would you like to insert into the table?",
                    "actions": []
                }
            
            # Insert the data
            row_id = ModuleManager.insert_data(
                module=module,
                table_name=table_name,
                data=data
            )
            
            # Generate a response
            if row_id > 0:
                response_content = f"""
                I've successfully added the data to the "{table_name}" table.
                
                The new record has ID: {row_id}
                
                Would you like to add more data or query the table?
                """
            else:
                response_content = """
                I'm sorry, I couldn't add the data to the table. There might be an issue with the data format or table structure.
                
                Could you provide the data in a more structured way?
                """
            
            return {
                "content": response_content,
                "actions": [
                    {
                        "type": "data_inserted",
                        "data": {
                            "table_name": table_name,
                            "row_id": row_id,
                            "success": row_id > 0
                        }
                    }
                ]
            }
            
        except Exception as e:
            logger.error(f"Error handling insert_data intent: {str(e)}")
            return {
                "content": "I encountered an error while trying to insert the data. Please try again with more specific details.",
                "actions": []
            }