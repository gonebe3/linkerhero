import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import the create_app function from your app package
from app import create_app

# Create the WSGI callable application instance
application = create_app()

if __name__ == '__main__':
    application.run() 