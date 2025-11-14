# app.py
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- Konfiguration ---
app.config["SECRET_KEY"] = "dev-secret-change-me"             
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///site.db"    # DB-Datei im Projektordner
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

with app.app_context():
    db.create_all()



class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw: str) -> None:
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw: str) -> bool:
        return check_password_hash(self.password_hash, pw)


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = (request.form.get("password") or "").strip()

        # einfache Validierung
        if not username:
            error = "Bitte einen Benutzernamen eingeben."
        elif len(password) < 6:
            error = "Passwort muss mindestens 6 Zeichen haben."
        elif User.query.filter_by(username=username).first():
            error = "Dieser Benutzername ist bereits vergeben."
        else:
            # Benutzer anlegen und speichern
            u = User(username=username)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            return redirect(url_for("register_ok"))

    # GET oder Fehlerfall -> Seite erneut rendern
    return render_template("register.html", error=error)

@app.route("/register/ok")
def register_ok():
    return render_template("register_ok.html")

# Hilfsroute zum Prüfen (optional):
@app.route("/users")
def users():
    return {"users": [{"id": u.id, "username": u.username} for u in User.query.order_by(User.id).all()]}

# --- Start ---
if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Tabellen erzeugen, falls noch nicht vorhanden
    app.run(debug=True)
