from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import requests
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Nutritionix API Keys
API_URL = "https://trackapi.nutritionix.com/v2/natural/nutrients"
HEADERS = {
    "x-app-id": "3486324a",
    "x-app-key": "6ecc62cc99ad39d61f1669bf4ea005ee",
    "Content-Type": "application/json"
}


# ---------- DATABASE SETUP ----------
def init_db():
    conn = sqlite3.connect('cedhealth.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            weight_goal REAL,
            calorie_goal INTEGER,
            protein_goal REAL,
            carbs_goal REAL,
            fat_goal REAL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            meal_name TEXT,
            calories REAL,
            protein REAL,
            fat REAL,
            carbs REAL,
            date TEXT,
            quantity REAL,
            unit TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS weight_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            weight REAL,
            date TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Add columns if they don't exist (for existing databases)
    try:
        c.execute('ALTER TABLE meals ADD COLUMN quantity REAL')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        c.execute('ALTER TABLE meals ADD COLUMN unit TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add macronutrient goal columns if they don't exist
    try:
        c.execute('ALTER TABLE goals ADD COLUMN protein_goal REAL')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        c.execute('ALTER TABLE goals ADD COLUMN carbs_goal REAL')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        c.execute('ALTER TABLE goals ADD COLUMN fat_goal REAL')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    conn.commit()
    conn.close()


init_db()


# ---------- ROUTES ----------
@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('cedhealth.db')
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE username = ? AND password = ?',
                  (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = user[0]
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid username or password'
    return render_template('login.html', error=error)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            conn = sqlite3.connect('cedhealth.db')
            c = conn.cursor()
            c.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                      (username, password))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            error = 'Username already exists.'
    return render_template('signup.html', error=error)


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = sqlite3.connect('cedhealth.db')
    c = conn.cursor()

    # Get user's goals
    c.execute('SELECT weight_goal, calorie_goal FROM goals WHERE user_id = ?', (user_id,))
    goal = c.fetchone()

    # Get meal statistics
    c.execute('SELECT COUNT(*) FROM meals WHERE user_id = ?', (user_id,))
    total_meals = c.fetchone()[0]

    # Calculate average daily calories
    c.execute('SELECT AVG(calories) FROM meals WHERE user_id = ?', (user_id,))
    avg_calories_result = c.fetchone()[0]
    avg_daily_calories = int(avg_calories_result) if avg_calories_result else 0

    # Get daily calories for the past 7 days
    c.execute('''
        SELECT date, SUM(calories) 
        FROM meals 
        WHERE user_id = ? 
        AND date >= date('now', '-7 days')
        GROUP BY date 
        ORDER BY date
    ''', (user_id,))
    daily_calories = c.fetchall()

    # Get daily weight for the past 7 days
    c.execute('''
        SELECT date, weight 
        FROM weight_logs 
        WHERE user_id = ? 
        AND date >= date('now', '-7 days')
        ORDER BY date
    ''', (user_id,))
    daily_weights = c.fetchall()

    conn.close()

    return render_template('dashboard.html', 
                         username=session['username'],
                         goal=goal,
                         total_meals=total_meals,
                         avg_daily_calories=avg_daily_calories,
                         daily_calories=daily_calories,
                         daily_weights=daily_weights)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/goals', methods=['GET', 'POST'])
def goals():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = sqlite3.connect('cedhealth.db')
    c = conn.cursor()
    if request.method == 'POST':
        weight_goal = request.form.get('weight_goal', type=float)
        calorie_goal = request.form.get('calorie_goal', type=int)
        protein_goal = request.form.get('protein_goal', type=float)
        carbs_goal = request.form.get('carbs_goal', type=float)
        fat_goal = request.form.get('fat_goal', type=float)
        c.execute('DELETE FROM goals WHERE user_id = ?', (user_id, ))
        c.execute(
            'INSERT INTO goals (user_id, weight_goal, calorie_goal, protein_goal, carbs_goal, fat_goal) VALUES (?, ?, ?, ?, ?, ?)',
            (user_id, weight_goal, calorie_goal, protein_goal, carbs_goal, fat_goal))
        conn.commit()
    c.execute('SELECT weight_goal, calorie_goal, protein_goal, carbs_goal, fat_goal FROM goals WHERE user_id = ?',
              (user_id, ))
    goal = c.fetchone()
    conn.close()
    return render_template('goals.html', goal=goal)


@app.route('/analyze_meal', methods=['GET', 'POST'])
def analyze_meal():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    nutrition_data = None
    error_message = None

    if request.method == 'POST':
        meal_name = request.form.get('meal_name')
        if meal_name:
            try:
                response = requests.post(API_URL,
                                         headers=HEADERS,
                                         json={"query": meal_name})
                data = response.json()
                if 'foods' in data:
                    food = data['foods'][0]
                    nutrition_data = {
                        'name': food['food_name'],
                        'calories': food['nf_calories'],
                        'protein': food['nf_protein'],
                        'fat': food['nf_total_fat'],
                        'carbs': food['nf_total_carbohydrate']
                    }

                    # Save to DB
                    conn = sqlite3.connect('cedhealth.db')
                    c = conn.cursor()
                    c.execute(
                        '''
                        INSERT INTO meals (user_id, meal_name, calories, protein, fat, carbs, date)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''',
                        (session['user_id'], nutrition_data['name'],
                         nutrition_data['calories'], nutrition_data['protein'],
                         nutrition_data['fat'], nutrition_data['carbs'],
                         datetime.now().date().isoformat()))
                    conn.commit()
                    conn.close()
                else:
                    error_message = "Nutrition data not found."
            except Exception as e:
                error_message = str(e)
        else:
            error_message = "Please enter a meal name."

    return render_template('analyze_meal.html',
                           nutrition_data=nutrition_data,
                           error_message=error_message)


@app.route('/meals', methods=['GET', 'POST'])
def meals():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    nutrition_data = None
    error_message = None

    # Handle adding new meal
    if request.method == 'POST' and request.form.get('action') == 'add_meal':
        quantity = request.form.get('quantity')
        unit = request.form.get('unit')
        food_name = request.form.get('food_name')

        if quantity and unit and food_name:
            # Combine quantity, unit, and food name for API query
            meal_query = f"{quantity} {unit} {food_name}"
            try:
                response = requests.post(API_URL,
                                         headers=HEADERS,
                                         json={"query": meal_query})
                data = response.json()
                if 'foods' in data:
                    food = data['foods'][0]
                    nutrition_data = {
                        'name': food['food_name'],
                        'calories': food['nf_calories'],
                        'protein': food['nf_protein'],
                        'fat': food['nf_total_fat'],
                        'carbs': food['nf_total_carbohydrate']
                    }

                    # Save to DB
                    conn = sqlite3.connect('cedhealth.db')
                    c = conn.cursor()
                    c.execute(
                        '''
                        INSERT INTO meals (user_id, meal_name, calories, protein, fat, carbs, date, quantity, unit)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                        (session['user_id'], nutrition_data['name'],
                         nutrition_data['calories'], nutrition_data['protein'],
                         nutrition_data['fat'], nutrition_data['carbs'],
                         datetime.now().date().isoformat(), float(quantity), unit))
                    conn.commit()
                    conn.close()
                else:
                    error_message = "Nutrition data not found."
            except Exception as e:
                error_message = str(e)
        else:
            error_message = "Please enter quantity, unit, and food name."

    # Get meals for display
    date_filter = request.args.get('date')
    user_id = session['user_id']
    conn = sqlite3.connect('cedhealth.db')
    c = conn.cursor()
    if date_filter:
        c.execute('SELECT * FROM meals WHERE user_id = ? AND date = ?',
                  (user_id, date_filter))
    else:
        c.execute('SELECT * FROM meals WHERE user_id = ?', (user_id, ))
    meals_by_user = c.fetchall()
    
    # Get macronutrient totals for filtered meals
    if date_filter:
        c.execute('SELECT SUM(protein), SUM(carbs), SUM(fat) FROM meals WHERE user_id = ? AND date = ?',
                  (user_id, date_filter))
    else:
        c.execute('SELECT SUM(protein), SUM(carbs), SUM(fat) FROM meals WHERE user_id = ?', (user_id, ))
    macro_totals = c.fetchone()
    
    # Get user's macronutrient goals
    c.execute('SELECT protein_goal, carbs_goal, fat_goal FROM goals WHERE user_id = ?', (user_id,))
    macro_goals = c.fetchone()
    
    conn.close()

    return render_template('meals.html',
                           meals=meals_by_user,
                           selected_date=date_filter,
                           nutrition_data=nutrition_data,
                           error_message=error_message,
                           macro_totals=macro_totals,
                           macro_goals=macro_goals)


@app.route('/delete_meal/<int:meal_id>', methods=['GET', 'POST'])
def delete_meal(meal_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('cedhealth.db')
    c = conn.cursor()
    c.execute('DELETE FROM meals WHERE id = ? AND user_id = ?',
              (meal_id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('meals'))


@app.route('/log_weight', methods=['POST'])
def log_weight():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    weight = request.form.get('weight', type=float)
    if weight:
        conn = sqlite3.connect('cedhealth.db')
        c = conn.cursor()
        
        # Delete existing weight log for today if it exists
        today = datetime.now().date().isoformat()
        c.execute('DELETE FROM weight_logs WHERE user_id = ? AND date = ?',
                  (session['user_id'], today))
        
        # Insert new weight log
        c.execute('INSERT INTO weight_logs (user_id, weight, date) VALUES (?, ?, ?)',
                  (session['user_id'], weight, today))
        conn.commit()
        conn.close()

    return redirect(url_for('dashboard'))


# ---------- RUN ----------
if __name__ == '__main__':
    app.run(debug=True)