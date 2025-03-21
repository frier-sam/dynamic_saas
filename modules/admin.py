from django.contrib import admin

# Register your models here.
from .models import Module,ModuleState,DynamicTable

admin.site.register(Module)
admin.site.register(ModuleState)
admin.site.register(DynamicTable)

