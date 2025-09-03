"""
Script para iniciar la aplicación simplificada
"""
import os
from datetime import datetime
from app import app

# Añadir la función now para utilizarla en las plantillas
@app.context_processor
def utility_processor():
    def now():
        return datetime.now()
    return dict(now=now)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
