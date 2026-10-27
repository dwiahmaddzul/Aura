"""
Aura Social — API Package
Aggregates all Flask blueprints.
"""
from api.posts import bp as posts_bp
from api.stories import bp as stories_bp
from api.profiles import bp as profiles_bp
from api.dm import bp as dm_bp
from api.me import bp as me_bp
from api.notif_search import bp as notif_search_bp
from api.media_bp import bp as media_bp
from api.kelola import bp as kelola_bp


def register_blueprints(app):
    """Register all API blueprints on the Flask app."""
    for bp in (posts_bp, stories_bp, profiles_bp, dm_bp, me_bp, notif_search_bp,
               media_bp, kelola_bp):
        app.register_blueprint(bp)
