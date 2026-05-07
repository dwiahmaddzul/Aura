"""
Aura Social — API Package
Aggregates all Flask blueprints.
"""
from api.posts import bp as posts_bp
from api.stories import bp as stories_bp
from api.profiles import bp as profiles_bp
from api.dm import bp as dm_bp
from api.me import bp as me_bp


def register_blueprints(app):
    """Register all API blueprints on the Flask app."""
    app.register_blueprint(posts_bp)
    app.register_blueprint(stories_bp)
    app.register_blueprint(profiles_bp)
    app.register_blueprint(dm_bp)
    app.register_blueprint(me_bp)
