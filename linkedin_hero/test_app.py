from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return '<h1>LinkedIn Hero Test - Flask is working!</h1><p>If you see this, Flask is running correctly.</p>'

if __name__ == '__main__':
    app.run(debug=True) 