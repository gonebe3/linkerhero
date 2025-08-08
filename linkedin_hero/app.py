from app import create_app

# Create the Flask application instance
app = create_app()

# This is the WSGI callable that cPanel will use
application = app

if __name__ == '__main__':
    app.run() 