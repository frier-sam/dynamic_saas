import json
from django.db import models
from django.contrib.auth.models import User


class Module(models.Model):
    """Represents a dynamic module created for a user"""
    
    MODULE_TYPES = (
        ('data', 'Data Management'),
        ('form', 'Form Interface'),
        ('report', 'Reporting'),
        ('dashboard', 'Dashboard'),
        ('custom', 'Custom Type'),
    )
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='modules')
    module_type = models.CharField(max_length=20, choices=MODULE_TYPES, default='custom')
    has_gui = models.BooleanField(default=False)
    
    # Store the module's schema and configuration as JSON
    schema = models.TextField(default='{}')
    config = models.TextField(default='{}')
    
    # UI components and layout stored as JSON
    ui_definition = models.TextField(default='{}')
    
    # Creation and modification timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'name')
    
    def __str__(self):
        return f"{self.name} ({self.user.username})"
    
    def get_schema(self):
        """Returns the schema as a Python dictionary"""
        return json.loads(self.schema)
    
    def set_schema(self, schema_dict):
        """Sets the schema from a Python dictionary"""
        self.schema = json.dumps(schema_dict)
    
    def get_config(self):
        """Returns the config as a Python dictionary"""
        return json.loads(self.config)
    
    def set_config(self, config_dict):
        """Sets the config from a Python dictionary"""
        self.config = json.dumps(config_dict)
    
    def get_ui_definition(self):
        """Returns the UI definition as a Python dictionary"""
        return json.loads(self.ui_definition)
    
    def set_ui_definition(self, ui_dict):
        """Sets the UI definition from a Python dictionary"""
        self.ui_definition = json.dumps(ui_dict)


class DynamicTable(models.Model):
    """Represents a dynamically created database table"""
    
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='tables')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    
    # Table schema stored as JSON
    schema = models.TextField(default='{}')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('module', 'name')
    
    def __str__(self):
        return f"{self.name} ({self.module.name})"
    
    def get_schema(self):
        """Returns the schema as a Python dictionary"""
        return json.loads(self.schema)
    
    def set_schema(self, schema_dict):
        """Sets the schema from a Python dictionary"""
        self.schema = json.dumps(schema_dict)


class ModuleState(models.Model):
    """Stores the current state and history of a module's usage"""
    
    module = models.OneToOneField(Module, on_delete=models.CASCADE, related_name='state')
    is_active = models.BooleanField(default=True)
    last_accessed = models.DateTimeField(auto_now=True)
    usage_count = models.IntegerField(default=0)
    
    # Module state stored as JSON
    state_data = models.TextField(default='{}')
    
    def __str__(self):
        return f"State for {self.module.name}"
    
    def get_state_data(self):
        """Returns the state data as a Python dictionary"""
        return json.loads(self.state_data)
    
    def set_state_data(self, state_dict):
        """Sets the state data from a Python dictionary"""
        self.state_data = json.dumps(state_dict)
        
    def increment_usage(self):
        """Increment usage count"""
        self.usage_count += 1
        self.save()