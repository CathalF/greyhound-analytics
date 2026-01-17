"""
Greyhound Racing Value Finder - Flask Web Application

Main application entry point for the web dashboard displaying races,
dog statistics, odds comparison, and value bet identification.
"""

from flask import Flask
import os

# Create Flask app
app = Flask(__name__,
            template_folder='templates',
            static_folder='static')

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'True') == 'True'

# Import and register blueprints
from src.routes import dashboard, races, api
from src.routes.patterns import patterns_bp

app.register_blueprint(dashboard.bp)
app.register_blueprint(races.bp)
app.register_blueprint(api.bp)
app.register_blueprint(patterns_bp)


@app.route('/health')
def health_check():
    """Health check endpoint"""
    return {'status': 'ok', 'message': 'Greyhound Racing Value Finder is running'}


if __name__ == '__main__':
    # Run development server
    app.run(host='0.0.0.0', port=5000, debug=True)
