from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from jinja2 import DictLoader
from datetime import datetime, date, timedelta
import os

app = Flask(__name__)

# --- CONFIGURATION ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'organizer.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'random_key' # <-- NEED EDITION

db = SQLAlchemy(app)

# --- MODÈLES ---
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='A faire')
    priority = db.Column(db.String(20), default='Moyen')
    category = db.Column(db.String(50), default='Général')
    deadline = db.Column(db.Date, nullable=True)

    def get_smart_score(self):
        """Calcul d'un score pour le tri intelligent"""
        score = 0

        # 1. Poids de la priorité
        prio_weights = {'Urgent': 50, 'Moyen': 20, 'Pas-urgent': 0}
        score += prio_weights.get(self.priority, 0)

        # 2. Poids de la date (Plus c'est proche, plus le score monte)
        if self.deadline:
            delta = (self.deadline - date.today()).days
            if delta < 0: score += 1000  # EN RETARD !
            elif delta == 0: score += 500 # C'est pour aujourd'hui
            elif delta <= 2: score += 100 # C'est chaud (J+1, J+2)
            elif delta <= 7: score += 50  # Cette semaine
            else: score -= delta # Plus c'est loin, moins c'est urgent

        # 3. Bonus si "En cours"
        if self.status == 'En cours':
            score += 15

        return score

    def friendly_date(self):
        """Retourne une date lisible pour l'humain"""
        if not self.deadline: return "Pas de date"
        delta = (self.deadline - date.today()).days
        if delta < 0: return f"Retard de {abs(delta)}j !"
        if delta == 0: return "Aujourd'hui !"
        if delta == 1: return "Demain"
        if 2 <= delta <= 7: return f"Dans {delta} jours"
        return self.deadline.strftime('%d/%m')

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- CSS AMÉLIORÉ (Mobile First) ---
USER_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');

    * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
    body {
        font-family: 'Poppins', sans-serif;
        margin: 0; padding: 0;
        min-height: 100vh;
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        color: #fff;
        padding-bottom: 90px; /* Espace pour la navbar mobile */
    }

    .container { width: 94%; max-width: 800px; margin: 20px auto; }

    /* --- NAVBAR --- */
    .navbar {
        background: rgba(0,0,0,0.3);
        padding: 15px 25px;
        border-radius: 16px;
        margin-bottom: 25px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        backdrop-filter: blur(10px);
    }
    .nav-links a {
        color: white; text-decoration: none; font-weight: bold;
        margin-left: 20px; padding: 8px 15px; border-radius: 20px;
        transition: 0.2s;
    }
    .nav-links a:hover, .nav-links a.active { background: rgba(255,255,255,0.2); }

    /* --- MOBILE NAV (Bottom Bar) --- */
    @media (max-width: 768px) {
        .navbar { display: none; } /* On cache la navbar du haut */
        .mobile-nav {
            position: fixed; bottom: 0; left: 0; width: 100%;
            background: #1a1a2e;
            display: flex; justify-content: space-around;
            padding: 15px 0;
            border-top: 1px solid rgba(255,255,255,0.1);
            z-index: 1000;
            box-shadow: 0 -5px 20px rgba(0,0,0,0.5);
        }
        .mobile-nav a {
            color: rgba(255,255,255,0.6); text-decoration: none;
            display: flex; flex-direction: column; align-items: center;
            font-size: 0.8em;
        }
        .mobile-nav a.active { color: #4facfe; transform: scale(1.1); }
        .mobile-nav span { font-size: 1.4em; margin-bottom: 2px; }
    }
    @media (min-width: 769px) { .mobile-nav { display: none; } }

    /* --- CARDS & GLASS --- */
    .glass-panel {
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
    }

    /* Tâches */
    .task-card {
        background: rgba(0,0,0,0.25);
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 12px;
        position: relative;
        border-left: 6px solid #ccc;
        transition: transform 0.2s;
        display: flex; justify-content: space-between; align-items: center;
    }
    .task-card:active { transform: scale(0.98); } /* Effet tactile */

    .prio-Urgent { border-left-color: #ff416c; background: linear-gradient(90deg, rgba(255,65,108,0.1), transparent); }
    .prio-Moyen { border-left-color: #ffbd39; }
    .prio-Pas-urgent { border-left-color: #00b09b; }
    .status-Fait { opacity: 0.5; filter: grayscale(1); }

    /* Formulaires */
    input, select, textarea {
        padding: 15px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.2);
        background: rgba(0,0,0,0.2); color: #fff; outline: none; width: 100%; margin-bottom: 15px;
        font-size: 16px; /* Evite le zoom auto sur iPhone */
    }
    option { background: #333; color: white; }

    /* Boutons */
    .btn {
        padding: 10px 20px; border-radius: 50px; cursor: pointer; border: none;
        text-decoration: none; display: inline-flex; align-items: center; justify-content: center;
        font-weight: 600; transition: 0.3s; color: white; margin: 2px;
    }
    .btn-add { background: #00b09b; width: 100%; padding: 15px; font-size: 1.1em; }
    .btn-icon { width: 35px; height: 35px; padding: 0; border-radius: 50%; background: rgba(255,255,255,0.1); font-size: 1.2em; }
    .btn-small { font-size: 0.8em; padding: 5px 12px; background: rgba(255,255,255,0.15); }

    /* Headers */
    h2 { font-size: 1.4em; border-bottom: 2px solid rgba(255,255,255,0.1); padding-bottom: 10px; margin-top:0; }
    .badge { padding: 4px 8px; border-radius: 6px; font-size: 0.75em; background: rgba(0,0,0,0.3); }
    .badge-date { color: #ffbd39; font-weight: bold; }

    .flex-row { display: flex; gap: 10px; }
    @media (max-width: 768px) { .flex-row { flex-direction: column; gap: 0; } }
</style>
"""

# --- TEMPLATES HTML ---

LAYOUT_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Organizer 2.0</title>
    """ + USER_CSS + """
</head>
<body>
    <div class="container">
        <div class="navbar">
            <div style="font-size:1.2em;">🚀 <b>Organizer</b></div>
            <div class="nav-links">
                <a href="/" class="{{ 'active' if request.path == '/' }}">Dashboard</a>
                <a href="/todo" class="{{ 'active' if request.path == '/todo' }}">Tâches</a>
                <a href="/notes" class="{{ 'active' if request.path == '/notes' }}">Notes</a>
            </div>
        </div>

        {% block content %}{% endblock %}
    </div>

    <div class="mobile-nav">
        <a href="/" class="{{ 'active' if request.path == '/' }}"><span>📊</span>Accueil</a>
        <a href="/todo" class="{{ 'active' if request.path == '/todo' }}"><span>✅</span>Tâches</a>
        <a href="/notes" class="{{ 'active' if request.path == '/notes' }}"><span>📝</span>Notes</a>
    </div>
</body>
</html>
"""

INDEX_HTML = """
{% extends "layout.html" %}
{% block content %}
<div class="glass-panel">
    <h2>🔥 Urgences du jour</h2>
    {% if tasks %}
        {% for task in tasks %}
        <div class="task-card prio-{{ task.priority }}">
            <div>
                <div style="font-weight:bold; font-size:1.1em;">{{ task.content }}</div>
                <div style="margin-top:5px;">
                    <span class="badge badge-date">⏰ {{ task.friendly_date() }}</span>
                    <span class="badge">{{ task.category }}</span>
                </div>
            </div>
            <a href="/update_status/{{ task.id }}/Fait" class="btn btn-icon" style="color:#4caf50;">✔</a>
        </div>
        {% endfor %}
    {% else %}
        <div style="text-align:center; padding:20px;">
            <div style="font-size:3em;">🎉</div>
            <p>Rien d'urgent. Profite !</p>
        </div>
    {% endif %}
    <a href="/todo" class="btn btn-add" style="margin-top:10px; background:rgba(255,255,255,0.1);">Voir toutes les tâches</a>
</div>

<div class="glass-panel">
    <h2>💡 Dernière pensée</h2>
    {% if note %}
        <p style="font-style:italic; font-size:1.1em;">"{{ note.content }}"</p>
        <div style="text-align:right;">
            <a href="/notes" class="btn btn-small">Voir les notes</a>
        </div>
    {% else %}
        <p>Pas encore de notes.</p>
    {% endif %}
</div>
{% endblock %}
"""

TODO_HTML = """
{% extends "layout.html" %}
{% block content %}
<div class="glass-panel">
    <details>
        <summary class="btn btn-add" style="list-style:none; text-align:center;">+ Nouvelle Tâche</summary>
        <form action="/add_task" method="POST" style="margin-top: 15px;">
            <input type="text" name="content" placeholder="Qu'est-ce qu'il faut faire ?" required>
            <div class="flex-row" style="gap:10px;">
                <select name="priority">
                    <option value="Urgent">🔴 Urgent</option>
                    <option value="Moyen" selected>🟠 Moyen</option>
                    <option value="Pas-urgent">🟢 Pas urgent</option>
                </select>
                <select name="category">
                    <option value="Général">📂 Général</option>
                    <option value="Travail">💼 Travail</option>
                    <option value="Perso">🏠 Perso</option>
                    <option value="Courses">🛒 Courses</option>
                </select>
            </div>
            <input type="date" name="deadline">
            <button type="submit" class="btn btn-add" style="background: #4facfe;">Sauvegarder</button>
        </form>
    </details>
</div>

<div style="display:flex; gap:5px; overflow-x:auto; padding-bottom:10px; margin-bottom:10px;">
    <a href="/todo" class="badge" style="text-decoration:none; color:white; border:1px solid white;">Tout</a>
    <a href="/todo?cat=Travail" class="badge" style="text-decoration:none; color:white; border:1px solid white;">Travail</a>
    <a href="/todo?cat=Perso" class="badge" style="text-decoration:none; color:white; border:1px solid white;">Perso</a>
</div>

<div style="padding-bottom: 50px;">
    {% for task in tasks %}
    <div class="task-card prio-{{ task.priority }} status-{{ task.status }}">
        <div style="flex:1;">
            <div style="font-size:1.1em; font-weight:600; display:flex; align-items:center; gap:5px;">
                {% if task.priority == 'Urgent' %}🔴{% endif %}
                {{ task.content }}
            </div>
            <div style="font-size:0.85em; opacity:0.8; margin-top:4px;">
                <span class="badge badge-date">{{ task.friendly_date() }}</span>
                <span class="badge">{{ task.status }}</span>
            </div>
        </div>

        <div style="display:flex; flex-direction:column; gap:5px;">
            {% if task.status != 'Fait' %}
                <a href="/update_status/{{ task.id }}/Fait" class="btn btn-icon" style="background:#4caf50;">✔</a>
            {% endif %}
            <a href="/edit_task/{{ task.id }}" class="btn btn-icon" style="background:#ffa726;">✏️</a>
            <a href="/delete_task/{{ task.id }}" class="btn btn-icon" style="background:#ef5350;">🗑</a>
        </div>
    </div>
    {% endfor %}
</div>
{% endblock %}
"""

EDIT_TASK_HTML = """
{% extends "layout.html" %}
{% block content %}
<div class="glass-panel">
    <h2>✏️ Modifier la tâche</h2>
    <form action="/edit_task/{{ task.id }}" method="POST">
        <label>Titre</label>
        <input type="text" name="content" value="{{ task.content }}" required>

        <label>Priorité</label>
        <select name="priority">
            <option value="Urgent" {% if task.priority == 'Urgent' %}selected{% endif %}>🔴 Urgent</option>
            <option value="Moyen" {% if task.priority == 'Moyen' %}selected{% endif %}>🟠 Moyen</option>
            <option value="Pas-urgent" {% if task.priority == 'Pas-urgent' %}selected{% endif %}>🟢 Pas urgent</option>
        </select>

        <label>Catégorie</label>
        <select name="category">
            <option value="Général" {% if task.category == 'Général' %}selected{% endif %}>📂 Général</option>
            <option value="Travail" {% if task.category == 'Travail' %}selected{% endif %}>💼 Travail</option>
            <option value="Perso" {% if task.category == 'Perso' %}selected{% endif %}>🏠 Perso</option>
            <option value="Courses" {% if task.category == 'Courses' %}selected{% endif %}>🛒 Courses</option>
        </select>

        <label>Date limite</label>
        <input type="date" name="deadline" value="{{ task.deadline }}">

        <div class="flex-row" style="margin-top:20px; gap:10px;">
            <a href="/todo" class="btn" style="background:#666; flex:1; text-align:center;">Annuler</a>
            <button type="submit" class="btn btn-add" style="flex:1;">Mettre à jour</button>
        </div>
    </form>
</div>
{% endblock %}
"""

NOTES_HTML = """
{% extends "layout.html" %}
{% block content %}
<div class="glass-panel">
    <form action="/add_note" method="POST">
        <textarea name="content" placeholder="Écrire une nouvelle note..." required></textarea>
        <button type="submit" class="btn btn-add">Ajouter Note</button>
    </form>
</div>

<div style="column-count: 1; column-gap: 15px;"> {% for note in notes %}
    <div class="glass-panel" style="display:inline-block; width:100%; text-align:left;">
        <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
            <small style="opacity:0.6;">{{ note.created_at.strftime('%d/%m %H:%M') }}</small>
            <div>
                <a href="/edit_note/{{ note.id }}" style="text-decoration:none; margin-right:10px;">✏️</a>
                <a href="/delete_note/{{ note.id }}" style="text-decoration:none; color:#ff6b6b;">✕</a>
            </div>
        </div>
        <p style="white-space: pre-wrap; margin:0;">{{ note.content }}</p>
    </div>
    {% endfor %}
</div>
{% endblock %}
"""

EDIT_NOTE_HTML = """
{% extends "layout.html" %}
{% block content %}
<div class="glass-panel">
    <h2>✏️ Modifier la note</h2>
    <form action="/edit_note/{{ note.id }}" method="POST">
        <textarea name="content" style="height:200px;" required>{{ note.content }}</textarea>
        <div class="flex-row" style="margin-top:20px; gap:10px;">
            <a href="/notes" class="btn" style="background:#666; flex:1; text-align:center;">Annuler</a>
            <button type="submit" class="btn btn-add" style="flex:1;">Mettre à jour</button>
        </div>
    </form>
</div>
{% endblock %}
"""

# --- LOADER TEMPLATES ---
templates = {
    'layout.html': LAYOUT_HTML,
    'index.html': INDEX_HTML,
    'todo.html': TODO_HTML,
    'edit_task.html': EDIT_TASK_HTML,
    'notes.html': NOTES_HTML,
    'edit_note.html': EDIT_NOTE_HTML
}
app.jinja_loader = DictLoader(templates)

# --- LOGIQUE ---

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    # Récupérer toutes les tâches non faites
    tasks = Task.query.filter(Task.status != 'Fait').all()
    # Trier par le "Smart Score" (le plus grand score en premier)
    tasks.sort(key=lambda x: x.get_smart_score(), reverse=True)

    last_note = Note.query.order_by(Note.created_at.desc()).first()
    return render_template('index.html', tasks=tasks[:3], note=last_note)

@app.route('/todo')
def todo():
    cat = request.args.get('cat')

    query = Task.query
    if cat: query = query.filter_by(category=cat)

    tasks = query.all()
    # Algorithme de Tri Puissant : Fait en bas, puis par Smart Score
    tasks.sort(key=lambda x: (x.status == 'Fait', -x.get_smart_score()))

    return render_template('todo.html', tasks=tasks)

@app.route('/add_task', methods=['POST'])
def add_task():
    d = request.form.get('deadline')
    date_obj = datetime.strptime(d, '%Y-%m-%d').date() if d else None

    new_task = Task(
        content=request.form['content'],
        priority=request.form['priority'],
        category=request.form['category'],
        deadline=date_obj
    )
    db.session.add(new_task)
    db.session.commit()
    return redirect(url_for('todo'))

@app.route('/edit_task/<int:id>', methods=['GET', 'POST'])
def edit_task(id):
    task = Task.query.get_or_404(id)
    if request.method == 'POST':
        task.content = request.form['content']
        task.priority = request.form['priority']
        task.category = request.form['category']
        d = request.form.get('deadline')
        task.deadline = datetime.strptime(d, '%Y-%m-%d').date() if d else None
        db.session.commit()
        return redirect(url_for('todo'))
    return render_template('edit_task.html', task=task)

@app.route('/update_status/<int:id>/<new_status>')
def update_status(id, new_status):
    task = Task.query.get_or_404(id)
    task.status = new_status
    db.session.commit()
    return redirect(request.referrer or url_for('todo'))

@app.route('/delete_task/<int:id>')
def delete_task(id):
    task = Task.query.get_or_404(id)
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for('todo'))

# --- NOTES ROUTES ---

@app.route('/notes')
def notes():
    notes = Note.query.order_by(Note.created_at.desc()).all()
    return render_template('notes.html', notes=notes)

@app.route('/add_note', methods=['POST'])
def add_note():
    new_note = Note(content=request.form['content'])
    db.session.add(new_note)
    db.session.commit()
    return redirect(url_for('notes'))

@app.route('/edit_note/<int:id>', methods=['GET', 'POST'])
def edit_note(id):
    note = Note.query.get_or_404(id)
    if request.method == 'POST':
        note.content = request.form['content']
        db.session.commit()
        return redirect(url_for('notes'))
    return render_template('edit_note.html', note=note)

@app.route('/delete_note/<int:id>')
def delete_note(id):
    note = Note.query.get_or_404(id)
    db.session.delete(note)
    db.session.commit()
    return redirect(url_for('notes'))

if __name__ == '__main__':
    app.run(debug=True)
