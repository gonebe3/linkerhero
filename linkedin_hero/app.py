from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>LinkedIn Hero - Test</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
            .success { color: green; font-size: 24px; }
        </style>
    </head>
    <body>
        <h1 class="success">✅ LinkedIn Hero is Working!</h1>
        <p>Flask application is running successfully.</p>
        <p>If you see this message, your Python environment is working correctly.</p>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run() 