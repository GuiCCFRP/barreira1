# app.py
from flask        import Flask
from config       import Config
from extensions   import db, login_manager

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # create tables
    with app.app_context():
        from models import User  
        db.create_all()

    # register blueprints
    from auth   import auth_bp
    from upload import upload_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(upload_bp)

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
