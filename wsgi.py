import os
from app import create_app

# WSGI application entrypoint for Gunicorn and production web servers
environment = os.getenv("FLASK_ENV", "production")
app = create_app(environment)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
