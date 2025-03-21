from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes

from .models import Module, DynamicTable, ModuleState
from .module_manager import ModuleManager
from chat.chat_service import ChatService

import json
import logging

logger = logging.getLogger(__name__)


@login_required
def module_list_view(request):
    """
    View for listing all modules
    
    Args:
        request: HTTP request
        
    Returns:
        HttpResponse: Rendered template
    """
    modules = Module.objects.filter(user=request.user).order_by('-updated_at')
    
    return render(request, 'modules/module_list.html', {
        'modules': modules
    })


@login_required
def module_detail_view(request, module_id):
    """
    View for displaying a single module
    
    Args:
        request: HTTP request
        module_id (int): ID of the module
        
    Returns:
        HttpResponse: Rendered template
    """
    module = get_object_or_404(Module, id=module_id, user=request.user)
    
    # Record module usage
    ModuleManager.record_module_usage(module)
    
    # Get tables for this module
    tables = module.tables.all()
    
    # Check if there's an existing conversation for this module
    conversation = None
    if hasattr(module, 'conversations'):
        conversation = module.conversations.filter(is_active=True).order_by('-updated_at').first()
    
    # If not, create a new conversation for this module
    if not conversation:
        chat_service = ChatService()
        conversation = chat_service.create_conversation(
            user=request.user,
            title=f"Conversation about {module.name}",
            module=module
        )
    
    return render(request, 'modules/module_detail.html', {
        'module': module,
        'tables': tables,
        'conversation': conversation
    })


class ModuleListAPI(APIView):
    """API view for listing and creating modules"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all modules for the user"""
        modules = Module.objects.filter(
            user=request.user
        ).order_by('-updated_at')
        
        # Serialize the modules
        data = []
        for module in modules:
            data.append({
                'id': module.id,
                'name': module.name,
                'description': module.description,
                'module_type': module.module_type,
                'has_gui': module.has_gui,
                'created_at': module.created_at,
                'updated_at': module.updated_at,
                'usage_count': module.state.usage_count
            })
        
        return Response(data)
    
    def post(self, request):
        """Create a new module"""
        name = request.data.get('name')
        description = request.data.get('description')
        module_type = request.data.get('module_type', 'custom')
        schema = request.data.get('schema')
        has_gui = request.data.get('has_gui', False)
        ui_definition = request.data.get('ui_definition')
        
        if not name:
            return Response(
                {'error': 'Module name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create the module
        module = ModuleManager.create_module(
            user=request.user,
            name=name,
            description=description,
            module_type=module_type,
            schema=schema,
            has_gui=has_gui,
            ui_definition=ui_definition
        )
        
        if not module:
            return Response(
                {'error': 'Error creating module'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Create tables if schema is provided
        tables_created = []
        if schema:
            for table_name, table_data in schema.items():
                if 'fields' in table_data:
                    table = ModuleManager.create_table_for_module(
                        module=module,
                        table_name=table_name,
                        fields=table_data['fields'],
                        description=f"Table for {table_name}"
                    )
                    
                    if table:
                        tables_created.append(table_name)
        
        return Response({
            'id': module.id,
            'name': module.name,
            'description': module.description,
            'module_type': module.module_type,
            'has_gui': module.has_gui,
            'created_at': module.created_at,
            'updated_at': module.updated_at,
            'tables_created': tables_created
        }, status=status.HTTP_201_CREATED)


class ModuleDetailAPI(APIView):
    """API view for retrieving, updating, and deleting a module"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, module_id):
        """Get a specific module"""
        try:
            module = Module.objects.get(
                id=module_id,
                user=request.user
            )
            
            # Get tables for this module
            tables_data = []
            for table in module.tables.all():
                tables_data.append({
                    'id': table.id,
                    'name': table.name,
                    'description': table.description,
                    'schema': table.get_schema(),
                    'created_at': table.created_at,
                    'updated_at': table.updated_at
                })
            
            return Response({
                'id': module.id,
                'name': module.name,
                'description': module.description,
                'module_type': module.module_type,
                'has_gui': module.has_gui,
                'schema': module.get_schema(),
                'ui_definition': module.get_ui_definition() if module.has_gui else None,
                'created_at': module.created_at,
                'updated_at': module.updated_at,
                'usage_count': module.state.usage_count,
                'tables': tables_data
            })
            
        except Module.DoesNotExist:
            return Response(
                {'error': 'Module not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def patch(self, request, module_id):
        """Update a module"""
        try:
            module = Module.objects.get(
                id=module_id,
                user=request.user
            )
            
            # Update fields
            if 'name' in request.data:
                module.name = request.data['name']
            
            if 'description' in request.data:
                module.description = request.data['description']
            
            if 'module_type' in request.data:
                module.module_type = request.data['module_type']
            
            if 'ui_definition' in request.data:
                ModuleManager.update_module_ui(module, request.data['ui_definition'])
            
            module.save()
            
            return Response({
                'id': module.id,
                'name': module.name,
                'description': module.description,
                'module_type': module.module_type,
                'has_gui': module.has_gui,
                'created_at': module.created_at,
                'updated_at': module.updated_at
            })
            
        except Module.DoesNotExist:
            return Response(
                {'error': 'Module not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def delete(self, request, module_id):
        """Delete a module"""
        try:
            module = Module.objects.get(
                id=module_id,
                user=request.user
            )
            
            # Delete the module
            success = ModuleManager.delete_module(module)
            
            if success:
                return Response(status=status.HTTP_204_NO_CONTENT)
            else:
                return Response(
                    {'error': 'Error deleting module'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
        except Module.DoesNotExist:
            return Response(
                {'error': 'Module not found'},
                status=status.HTTP_404_NOT_FOUND
            )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def module_data_api(request, module_id, table_name):
    """
    API for querying and inserting data into a module's table
    
    Args:
        request: HTTP request
        module_id (int): ID of the module
        table_name (str): Name of the table
        
    Returns:
        Response: JSON response with data or confirmation
    """
    try:
        module = Module.objects.get(
            id=module_id,
            user=request.user
        )
        
        # Handle GET request (query data)
        if request.method == 'GET':
            # Extract query parameters
            where = request.query_params.get('where')
            
            # Extract params if provided
            params = []
            if 'params' in request.query_params:
                try:
                    params = json.loads(request.query_params.get('params'))
                except json.JSONDecodeError:
                    pass
            
            limit = request.query_params.get('limit')
            order_by = request.query_params.get('order_by')
            
            # Query the data
            results = ModuleManager.query_data(
                module=module,
                table_name=table_name,
                where=where,
                params=params,
                limit=limit,
                order_by=order_by
            )
            
            return Response(results)
        
        # Handle POST request (insert data)
        elif request.method == 'POST':
            # Get the data to insert
            data = request.data
            
            if not data:
                return Response(
                    {'error': 'Data is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            print("module",module)
            print("table_name",table_name)
            print("data",data)
            # Insert the data
            row_id = ModuleManager.insert_data(
                module=module,
                table_name=table_name,
                data=data
            )
            
            if row_id > 0:
                return Response({
                    'row_id': row_id,
                    'message': 'Data inserted successfully'
                }, status=status.HTTP_201_CREATED)
            else:
                return Response(
                    {'error': 'Error inserting data'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
    except Module.DoesNotExist:
        return Response(
            {'error': 'Module not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error in module_data_api: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def module_data_record_api(request, module_id, table_name, record_id):
    """
    API for updating and deleting records in a module's table
    
    Args:
        request: HTTP request
        module_id (int): ID of the module
        table_name (str): Name of the table
        record_id (int): ID of the record
        
    Returns:
        Response: JSON response with confirmation
    """
    try:
        module = Module.objects.get(
            id=module_id,
            user=request.user
        )
        
        # Handle PUT request (update record)
        if request.method == 'PUT':
            # Get the data to update
            data = request.data
            
            if not data:
                return Response(
                    {'error': 'Data is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update the record
            rows_affected = ModuleManager.update_data(
                module=module,
                table_name=table_name,
                data=data,
                where="id = ?",
                params=[record_id]
            )
            
            if rows_affected > 0:
                return Response({
                    'rows_affected': rows_affected,
                    'message': 'Record updated successfully'
                })
            else:
                return Response(
                    {'error': 'Error updating record or record not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Handle DELETE request (delete record)
        elif request.method == 'DELETE':
            # Delete the record
            rows_affected = ModuleManager.delete_data(
                module=module,
                table_name=table_name,
                where="id = ?",
                params=[record_id]
            )
            
            if rows_affected > 0:
                return Response({
                    'rows_affected': rows_affected,
                    'message': 'Record deleted successfully'
                })
            else:
                return Response(
                    {'error': 'Error deleting record or record not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
    except Module.DoesNotExist:
        return Response(
            {'error': 'Module not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error in module_data_record_api: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_ui_api(request, module_id):
    """
    API for generating a UI for a module
    
    Args:
        request: HTTP request
        module_id (int): ID of the module
        
    Returns:
        Response: JSON response with the generated UI definition
    """
    from chat.llm_service import ModuleAssistant
    
    try:
        module = Module.objects.get(
            id=module_id,
            user=request.user
        )
        
        # Generate UI definition
        module_assistant = ModuleAssistant()
        schema = module.get_schema()
        ui_definition = module_assistant.generate_ui_definition(module.name, schema)
        
        # Update the module
        success = ModuleManager.update_module_ui(module, ui_definition)
        
        if success:
            return Response({
                'ui_definition': ui_definition,
                'message': 'UI generated successfully'
            })
        else:
            return Response(
                {'error': 'Error generating UI'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    except Module.DoesNotExist:
        return Response(
            {'error': 'Module not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error in generate_ui_api: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )