from routes.core_routes import core_bp
from routes.auth_routes import auth_bp
from routes.pricechecker_routes import pricechecker_bp
from routes.matcher_routes import matcher_bp
from routes.lookup_routes import lookup_bp
from routes.records_routes import records_bp


def register_blueprints(app):
    app.register_blueprint(core_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(pricechecker_bp)
    app.register_blueprint(matcher_bp)
    app.register_blueprint(lookup_bp)
    app.register_blueprint(records_bp)
