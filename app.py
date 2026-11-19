from flask import Flask, render_template, jsonify
from pathlib import Path
import sqlite3

app = Flask(__name__)
DB = Path(__file__).parent / 'database' / 'svara.db'

def init_db():
    DB.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS languages (
            id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL)''')
        conn.executemany('INSERT OR IGNORE INTO languages(code,name) VALUES (?,?)', [
            ('ASL','American Sign Language'),('ISL','Indian Sign Language'),('BSL','British Sign Language')])

@app.get('/')
def home():
    return render_template('index.html', page='home')

@app.get('/recognize')
def recognize():
    return render_template('index.html', page='recognize')

@app.get('/translate')
def translate():
    return render_template('index.html', page='translate')

@app.get('/learn')
def learn():
    return render_template('index.html', page='learn')

@app.get('/api/languages')
def languages():
    with sqlite3.connect(DB) as conn:
        rows = conn.execute('SELECT code, name FROM languages ORDER BY id').fetchall()
    return jsonify([{'code': code, 'name': name} for code, name in rows])

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
