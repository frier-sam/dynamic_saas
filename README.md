# Dynamic SaaS 

A platform that enables users to create custom SaaS applications through natural language conversations with an AI assistant.

## Overview

The Dynamic SaaS  allows users to describe the application they need in natural language. The AI then:

1. Creates appropriate database structures
2. Generates user interfaces
3. Implements basic functionality
4. Allows for real-time modifications and evolution of the application

All of this happens through a conversational interface, making it accessible to users without technical expertise.

## Key Features

- **Conversational App Building**: Create applications by describing what you need
- **Dynamic Database Creation**: Automatically designed schemas based on requirements
- **Instant UI Generation**: Beautiful interfaces created for your data model
- **Real-time Customization**: Modify your app with simple natural language requests
- **Multi-Module Support**: Build complex applications with multiple components

## Technology Stack

- **Backend**: Django with REST Framework
- **Database**: SQLite 
- **AI**: Azure OpenAI (GPT-4o models)
- **Frontend**: HTML, Tailwind CSS, JavaScript

## Prerequisites

- Python 3.8+
- Azure OpenAI API access
- Basic understanding of web applications

## Installation

1. Clone this repository
   ```
   git clone https://github.com/yourusername/dynamic-saas-generator.git
   cd dynamic-saas-generator
   ```

2. Create a virtual environment
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file based on `.env.example` and add your Azure OpenAI credentials
   ```
   cp .env.example .env
   # Edit .env with your credentials
   ```

5. Run database migrations
   ```
   python manage.py migrate
   ```

6. Create a superuser
   ```
   python manage.py createsuperuser
   ```

7. Run the development server
   ```
   python manage.py runserver
   ```



## Usage

1. **Log in** to your account
2. **Start a conversation** with the AI assistant
3. **Describe the application** you want to build
4. **Follow the AI's guidance** to create and refine your application
5. **Use your generated modules** to manage your data

### Example Prompts
- "todo app with categories"
- "I want to create an invoice management system where I can track customers, products, and generate invoices with line items."
- "Can you help me build a simple CRM to track contacts, companies, deals, and activities?"
- "I need a task management tool with projects, tasks, due dates, and priority levels."
- "Can you create a user interface for my module? I need forms to add data and a dashboard to view records."

## Architecture

The system consists of several key components:

1. **User Authentication Layer**: Manages users and permissions
2. **Chat Interface**: Processes user requests and generates responses
3. **LLM Integration Service**: Communicates with Azure OpenAI
4. **Module Manager**: Creates and manages dynamic modules
5. **Database Manager**: Handles dynamic database operations
6. **UI Generator**: Creates user interfaces for modules


## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.


