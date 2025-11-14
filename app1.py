from templates import *
from ki import ask_deepseek



app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-change-me"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///site.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "static" / "avatars"
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2 MB Limit
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

db = SQLAlchemy(app)
# === Flask-Admin Setup ===

# =========================
# Datenbankmodelle
# =========================

class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False, default="Neuer Chat")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    messages = db.relationship(
        "ChatMessage",
        backref="chat",
        lazy=True,
        cascade="all, delete-orphan"
    )

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    avatar = db.Column(db.String(255))
    theme = db.Column(db.String(20), nullable=False, default="pink")
    is_admin = db.Column(db.Boolean, nullable=False, default=False)

    def set_password(self, pw: str) -> None:
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw: str) -> bool:
        return check_password_hash(self.password_hash, pw)

class LoginHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    username = db.Column(db.String(150), nullable=False)
    login_time = db.Column(db.DateTime, default=datetime.utcnow)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey("chat.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class SecureAdminIndex(AdminIndexView):
    def is_accessible(self):
        user_id = session.get("user_id")
        if not user_id:
            return False
        user = User.query.get(user_id)
        return user and user.username == "moddin123"

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for("anmelden", next="/admin"))

class SecureModelView(ModelView):
    def is_accessible(self):
        user_id = session.get("user_id")
        if not user_id:
            return False
        user = User.query.get(user_id)
        return user and user.username == "moddin123"

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for("anmelden", next="/admin"))

admin = Admin(
    app,
    name="Moddin Admin",
    template_mode="bootstrap4",
    index_view=SecureAdminIndex()
)

admin.add_view(SecureModelView(User, db.session))
admin.add_view(SecureModelView(Chat, db.session))
admin.add_view(SecureModelView(ChatMessage, db.session))
admin.add_view(SecureModelView(LoginHistory, db.session))


#========================
# Routen


@app.route("/")
def index():
    return render_template("index.html")


#========================
# Registrieren Seite
@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = (request.form.get("password") or "").strip()

        if not username:
            error = "Bitte einen Benutzernamen eingeben."
        elif len(password) < 6:
            error = "Passwort muss mindestens 6 Zeichen haben."
        elif User.query.filter_by(username=username).first():
            error = "Dieser Benutzername ist bereits vergeben."
        else:
            u = User(username=username)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            return redirect(url_for("register_ok"))

    return render_template("register.html", error=error)


#========================
#Register OK Seite

@app.route("/register/ok")
def register_ok():
    return render_template("register_ok.html")

#========================
# Anmelden Seite
@app.route("/anmelden", methods=["GET", "POST"])
def anmelden():
    error = ""
    next_url = request.args.get("next")
    blocked=session.get("login_blocked_until")
    if blocked and time()<blocked:
        error = "Zu viele fehlgeschlagene Anmeldeversuche. Bitte später erneut versuchen."
        return render_template("anmelden.html", error=error,next=next_url)

    if "login_versuche" not in session:
        session["login_versuche"] = 3

        
        
    
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = (request.form.get("password") or "").strip()

        user = User.query.filter_by(username=username).first()
        remember = bool(request.form.get("remember"))
        if user and user.check_password(password):
            session["user_id"] = user.id
            session.permanent = bool(remember)
            db.session.add(LoginHistory(user_id=user.id, username=user.username))
            db.session.commit()
            session["login_versuche"] = 3
            session.pop("login_blocked_until", None)
            return redirect(next_url or url_for("chatbot"))
        else:
            session["login_versuche"] -=1
            attempts = session["login_versuche"]

            if attempts<=0:
                error = "Zu viele fehlgeschlagene Anmeldeversuche. Bitte später erneut versuchen."
                session["login_blocked_until"]=time()+60
            else:
                error = "Ungültiger Benutzername oder Passwort.Sie haben noch %d Versuche" %attempts
    return render_template("anmelden.html", error=error, next=next_url)

#========================
# Logout Route
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("index"))
# =========================
#=========================
# Chatbot Seite
@app.route("/chatbot", methods=["GET","POST"])
def chatbot():
    if not session.get("user_id"):
        return redirect(url_for("anmelden"))
    user = User.query.get(session["user_id"])
    chats = (Chat.query
             .filter_by(user_id=user.id)
             .order_by(Chat.created_at.desc())
             .all())
    return render_template("Chatbot.html", user=user, chats=chats)

# =========================
# Profilseite (Avatar)
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if not session.get("user_id"):
        return redirect(url_for("anmelden"))
    user = User.query.get(session["user_id"])

    if request.method == "POST":
        file = request.files.get("avatar")
        if not file or file.filename == "":
            flash("Keine Datei ausgewählt.", "error")
        elif not allowed_file(file.filename):
            flash("Ungültiger Dateityp. Erlaubt sind: png, jpg, jpeg, gif, webp", "error")
        else:
            avatar_name = secure_filename(file.filename)
            ext = avatar_name.rsplit(".", 1)[1].lower()
            unique_name = f"user_{user.id}_{int(time())}.{ext}"

            if user.avatar:
                try:
                    old_path = os.path.join(app.config["UPLOAD_FOLDER"], os.path.basename(user.avatar))
                    if os.path.exists(old_path):
                        os.remove(old_path)
                except Exception:
                    pass

            save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
            file.save(save_path)
            user.avatar = f"avatars/{unique_name}"
            db.session.commit()
            flash("Datei erfolgreich hochgeladen!", "success")
            return redirect(url_for("profile"))

    return render_template("profil.html", user=user)

# =========================
# Chat API Routes

# Neue Chat erstellen
@app.route("/api/chats", methods=["POST"])
def api_new_chat():
    if not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401
    user_id = session["user_id"]
    count = Chat.query.filter_by(user_id=user_id).count()
    if count >= 20:
        return jsonify({"error": "Maximale Anzahl von 20 Chats erreicht."}), 400
    
    existing_chats = Chat.query.filter_by(user_id=user_id).count()
    title = f"Neuer Chat {existing_chats + 1}"
    
    c = Chat(user_id=user_id, title=title)
    db.session.add(c)
    db.session.commit()
    return jsonify({"id": c.id, "title": c.title, "created_at": c.created_at.isoformat()})
# =========================
# Liste aller Chats für den Benutzer
@app.route("/api/chats", methods=["GET"])
def api_list_chats():
    if not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401
    rows = (Chat.query
            .filter_by(user_id=session["user_id"])
            .order_by(Chat.created_at.desc())
            .all())
    return jsonify({"chats": [{"id": r.id, "title": r.title, "created": r.created_at.isoformat()} for r in rows]})
# =========================
# Alle Chats löschen 
@app.route("/admin/clear_chats")
def clear_chats():
 
    if not session.get("user_id"):
        return "Nicht erlaubt.", 403

    user_id = session.get("user_id")

  
    chats = Chat.query.filter_by(user_id=user_id).all()


    for c in chats:
        db.session.delete(c)

    db.session.commit()

   
    return redirect(url_for("chatbot"))


# =========================
# Einzelnen Chat löschen
@app.route("/api/chats/<int:chat_id>", methods=["DELETE"])
def delete_chat(chat_id):
    if not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401
    chat = Chat.query.filter_by(id=chat_id, user_id=session["user_id"]).first()
    if not chat:
        return jsonify({"error": "Chat nicht gefunden."}), 404
    db.session.delete(chat)
    db.session.commit()
    return jsonify({"message": "Chat erfolgreich gelöscht."})

# =========================
# Chat umbenennen
@app.route("/api/chats/<int:chat_id>", methods=["PUT"])
def rename_chat(chat_id):
    """Chat umbenennen"""
    if not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401
    
    try:
       
        data = request.get_json()
        if not data:
            return jsonify({"error": "Keine Daten erhalten"}), 400
            
        new_title = (data.get("title") or "").strip()
        if not new_title:
            return jsonify({"error": "Titel darf nicht leer sein"}), 400
        if len(new_title) > 150:
            return jsonify({"error": "Titel darf maximal 150 Zeichen lang sein"}), 400
            
        # Chat suchen
        chat = Chat.query.filter_by(id=chat_id, user_id=session["user_id"]).first()
        if not chat:
            return jsonify({"error": "Chat nicht gefunden."}), 404
            
        # Titel aktualisieren
        chat.title = new_title
        db.session.commit()
        
        # JSON zurückgeben
        return jsonify({
            "id": chat.id, 
            "title": chat.title, 
            "created_at": chat.created_at.isoformat()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Fehler beim Umbenennen: {e}")
        return jsonify({"error": f"Server Fehler: {str(e)}"}), 500


# =========================
# Farben API
@app.route("/api/farben", methods=["GET"])
def get_colours():
    if not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401
    user = User.query.get(session["user_id"])
    theme = getattr(user, "theme", "pink") or "pink"
    return jsonify({"theme": theme})

# =========================
# Set Farben API
@app.route("/api/farben", methods=["POST"])
def set_colours():
    if not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Keine Daten erhalten"}), 400
            
        theme = (data.get("theme") or "").strip().lower()
        allowed = {"pink", "blue", "dark"}
        if theme not in allowed:
            return jsonify({"error": "Ungültiges Theme. Erlaubt: pink, blue, dark."}), 400
            
        user = User.query.get(session["user_id"])
        user.theme = theme
        db.session.commit()
        return jsonify({"theme": theme})
        
    except Exception as e:
        return jsonify({"error": f"Server Fehler: {str(e)}"}), 500

# =========================
# Chat Messages API

@app.route("/api/chats/<int:chat_id>/messages", methods=["GET"])
def list_messages(chat_id):
    """Nachrichten eines Chats laden"""
    if not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401

    chat = Chat.query.filter_by(id=chat_id, user_id=session["user_id"]).first()
    if not chat:
        return jsonify({"error": "Chat nicht gefunden."}), 404

    rows = (ChatMessage.query
            .filter_by(chat_id=chat.id)                     
            .order_by(ChatMessage.created_at.asc())
            .all())

    return jsonify({
        "messages": [
            {
                "id": m.id,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
                "user_id": m.user_id
            }
            for m in rows
        ]
    })

# =========================
# Neue Nachricht erstellen + KI antworten lassen
@app.route("/api/chats/<int:chat_id>/messages", methods=["POST"])
def create_message(chat_id):
    """Neue Nachricht anlegen + KI antworten lassen"""
    if not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401

    chat = Chat.query.filter_by(id=chat_id, user_id=session["user_id"]).first()
    if not chat:
        return jsonify({"error": "Chat nicht gefunden."}), 404

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Keine Daten erhalten"}), 400

        text = (data.get("content") or "").strip()
        if not text:
            return jsonify({"error": "Nachricht darf nicht leer sein."}), 400

        # 1. User-Nachricht speichern
        msg = ChatMessage(chat_id=chat.id, user_id=session["user_id"], content=text)
        db.session.add(msg)
        db.session.commit()

        # 2. gesamten Chatverlauf laden (falls du ihn später nutzen willst)
        all_messages = ChatMessage.query.filter_by(
            chat_id=chat.id
        ).order_by(ChatMessage.created_at.asc()).all()

        
        messages_for_ai = []# Vorbereitung der Nachrichten für die KI
        for mi in all_messages:
            if mi.user_id == session["user_id"]:
                role = "user"
            else:
                role = "assistant"
            messages_for_ai.append({
                "role": role,
                "content": mi.content
            })

        # 3. System-Prompt für deine KI-Persönlichkeit
        system_prompt = """
Du bist Moddins KI-Bot.

Persönlichkeit:
- Du wirkst wie ein kluger, entspannter Freund.
- Du bist freundlich, humorvoll und gelegentlich leicht sarkastisch – aber nie verletzend.
- Du antwortest immer auf Deutsch.
- Du bist hilfsbereit und erklärst Dinge klar und verständlich.
- Du machst keine unnötig langen Texte. Präzise, aber nicht zu knapp.

Smalltalk:
- Du DARFST gelegentlich leichte Smalltalk-Elemente benutzen („klingt spannend“, „cooler Gedanke“, „was geht bei dir so?“).
- Aber du machst das NICHT ständig und NICHT mehrmals hintereinander.
- Du stellst keine aufdringlichen Fragen.
- Du verhältst dich wie ein normaler Mensch: locker, aber nicht pushy.

Identität:
- Wenn der Nutzer fragt „Wer bist du?“ oder „Wie heißt du?“ antwortest du:
  „Ich bin Moddins KI-Bot.“
- Du stellst dich NICHT selbstständig vor, außer der Nutzer fragt danach.

Stil:
- Maximal 1–2 passende Emojis, optional.
- Kein übertriebenes Motivieren, kein Kitsch, keine Zwangs-Fröhlichkeit.
- Wenn Sarkasmus, dann sehr leicht und freundlich.

Was du vermeiden sollst:
- Keine wiederholten Standardfloskeln wie „Wie kann ich dir heute helfen?“
- Kein künstliches „Wir lernen uns kennen“-Gerede.
- Kein übermäßiges Nachfragen.
- Keine langen Monologe.
- Keine ständig wiederkehrenden Vorschläge.

Ziel:
- Natürlich, locker, schlau und angenehm zu reden.


"""

        # 4. KI antworten lassen
        try:
            route=choose_model_for_prompt(text)
            model1=route["model"]
            use_deep_think=route["deep_think"]

            bot_reply, _think = ask_deepseek(
                input_content=text,
                system_prompt=system_prompt,
                model=model1,
                deep_think=use_deep_think,
            )
        except Exception as e:
            return jsonify({"error": f"KI Fehler: {str(e)}"}), 500

        # 5. KI-Antwort speichern
        bot_msg = ChatMessage(
            chat_id=chat.id,
            user_id=0,             # 0 = System / KI
            content=bot_reply
        )
        db.session.add(bot_msg)
        db.session.commit()

        # 6. Antwort ans Frontend
        return jsonify({
            "user_message": {
                "id": msg.id,
                "content": msg.content,
                "created_at": msg.created_at.isoformat()
            },
            "bot_message": {
                "id": bot_msg.id,
                "content": bot_msg.content,
                "created_at": bot_msg.created_at.isoformat()
            }
        }), 201

    except Exception as e:
        return jsonify({"error": f"Server Fehler: {str(e)}"}), 500

# =========================
# Modell Auswahl basierend auf dem Prompt
def choose_model_for_prompt(text:str):
    t=(text or "").lower()

    keywords=["warum", "wieso", "erklär", "erklärung",
        "analysiere", "analyse",
        "code", "python", "bug", "funktioniert nicht", "fehler",
        "mathe", "berechne", "rechnung", "algorithmus", "logik"]
    if any(k in t for k in keywords) or len(t)>200:
              return {
            "model": "deepseek-r1:8b",
            "deep_think": True
        }



    return {
        "model": "llama3.1:8b",
        "deep_think": False
    }




# Start
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)