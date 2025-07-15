from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import requests
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Nutritionix API Keys
API_URL = "https://trackapi.nutritionix.com/v2/natural/nutrients"
SEARCH_URL = "https://trackapi.nutritionix.com/v2/search/instant"
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
            meal_session_id TEXT,
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
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS saved_meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            meal_name TEXT,
            created_date TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS saved_meal_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            saved_meal_id INTEGER,
            food_name TEXT,
            quantity TEXT,
            calories REAL,
            protein REAL,
            fat REAL,
            carbs REAL,
            FOREIGN KEY (saved_meal_id) REFERENCES saved_meals(id)
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
    
    try:
        c.execute('ALTER TABLE meals ADD COLUMN meal_session_id TEXT')
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
    c.execute('SELECT weight_goal, calorie_goal, protein_goal, carbs_goal, fat_goal FROM goals WHERE user_id = ?', (user_id,))
    goal = c.fetchone()
    
    # Default values if no goals set
    calorie_goal = goal[1] if goal else 2000
    protein_goal = goal[2] if goal else 150
    carbs_goal = goal[3] if goal else 250
    fat_goal = goal[4] if goal else 65
    
    # Calculate fiber goal based on calorie goal (14g per 1000 calories)
    fiber_goal = round((calorie_goal / 1000) * 14, 1)

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

    # Get today's nutrition totals
    today = datetime.now().date().isoformat()
    c.execute('''
        SELECT SUM(protein), SUM(fat), SUM(carbs) 
        FROM meals 
        WHERE user_id = ? AND date = ?
    ''', (user_id, today))
    
    nutrition_totals = c.fetchone()
    current_protein = nutrition_totals[0] if nutrition_totals[0] else 0
    current_fat = nutrition_totals[1] if nutrition_totals[1] else 0
    current_carbs = nutrition_totals[2] if nutrition_totals[2] else 0
    
    # Calculate fiber (approximate: 3g per 100g carbs)
    current_fiber = round((current_carbs / 100) * 3, 1)

    # Calculate progress percentages
    protein_progress = min(100, (current_protein / protein_goal) * 100) if protein_goal > 0 else 0
    fat_progress = min(100, (current_fat / fat_goal) * 100) if fat_goal > 0 else 0
    carbs_progress = min(100, (current_carbs / carbs_goal) * 100) if carbs_goal > 0 else 0
    fiber_progress = min(100, (current_fiber / fiber_goal) * 100) if fiber_goal > 0 else 0

    conn.close()

    return render_template('dashboard.html', 
                         username=session['username'],
                         daily_calories=daily_calories,
                         daily_weights=daily_weights,
                         calorie_goal=calorie_goal,
                         protein_goal=protein_goal,
                         carbs_goal=carbs_goal,
                         fat_goal=fat_goal,
                         fiber_goal=fiber_goal,
                         current_protein=round(current_protein, 1),
                         current_fat=round(current_fat, 1),
                         current_carbs=round(current_carbs, 1),
                         current_fiber=current_fiber,
                         protein_progress=round(protein_progress, 1),
                         fat_progress=round(fat_progress, 1),
                         carbs_progress=round(carbs_progress, 1),
                         fiber_progress=round(fiber_progress, 1))


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


@app.route('/search_foods')
def search_foods():
    if 'user_id' not in session:
        return {'error': 'Not authenticated'}, 401
    
    query = request.args.get('q', '').strip()
    if not query:
        return {'common': [], 'branded': []}
    
    try:
        response = requests.get(SEARCH_URL, 
                               headers=HEADERS, 
                               params={'query': query})
        data = response.json()
        
        # Format the response for frontend
        result = {
            'common': [],
            'branded': []
        }
        
        if 'common' in data:
            for item in data['common'][:5]:  # Limit to 5 items
                result['common'].append({
                    'food_name': item['food_name'],
                    'tag_name': item.get('tag_name', ''),
                    'photo': item.get('photo', {}).get('thumb', '')
                })
        
        if 'branded' in data:
            for item in data['branded'][:5]:  # Limit to 5 items
                result['branded'].append({
                    'food_name': item['food_name'],
                    'brand_name': item.get('brand_name', ''),
                    'photo': item.get('photo', {}).get('thumb', '')
                })
        
        return result
    except Exception as e:
        return {'error': str(e)}, 500


@app.route('/analyze_meal', methods=['GET', 'POST'])
def analyze_meal():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    nutrition_data = []
    error_message = None
    total_nutrition = {'calories': 0, 'protein': 0, 'fat': 0, 'carbs': 0, 'fiber': 0}

    if request.method == 'POST':
        # Get all food items from the form
        food_items = []
        i = 0
        while True:
            food_item = request.form.get(f'food_item_{i}')
            if not food_item:
                break
            food_items.append(food_item.strip())
            i += 1
        
        if food_items:
            # Create a combined query for all items
            combined_query = ', '.join(food_items)
            
            try:
                response = requests.post(API_URL,
                                         headers=HEADERS,
                                         json={"query": combined_query})
                data = response.json()
                
                if 'foods' in data and data['foods']:
                    conn = sqlite3.connect('cedhealth.db')
                    c = conn.cursor()
                    current_date = datetime.now().date().isoformat()
                    
                    # Generate a unique meal session ID
                    import uuid
                    meal_session_id = str(uuid.uuid4())
                    
                    for food in data['foods']:
                        food_nutrition = {
                            'name': food['food_name'],
                            'calories': food['nf_calories'],
                            'protein': food['nf_protein'],
                            'fat': food['nf_total_fat'],
                            'carbs': food['nf_total_carbohydrate'],
                            'fiber': food.get('nf_dietary_fiber', 0)
                        }
                        
                        nutrition_data.append(food_nutrition)
                        
                        # Add to totals
                        total_nutrition['calories'] += food_nutrition['calories']
                        total_nutrition['protein'] += food_nutrition['protein']
                        total_nutrition['fat'] += food_nutrition['fat']
                        total_nutrition['carbs'] += food_nutrition['carbs']
                        total_nutrition['fiber'] += food_nutrition['fiber']

                        # Save to DB with meal session ID
                        c.execute(
                            '''
                            INSERT INTO meals (user_id, meal_name, calories, protein, fat, carbs, date, meal_session_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''',
                            (session['user_id'], food_nutrition['name'],
                             food_nutrition['calories'], food_nutrition['protein'],
                             food_nutrition['fat'], food_nutrition['carbs'],
                             current_date, meal_session_id))
                    
                    conn.commit()
                    conn.close()
                else:
                    error_message = "Nutrition data not found for the provided items."
            except Exception as e:
                error_message = f"Error processing meal: {str(e)}"
        else:
            error_message = "Please add at least one food item."

    return render_template('analyze_meal.html',
                           nutrition_data=nutrition_data,
                           total_nutrition=total_nutrition,
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


@app.route('/create_meal', methods=['GET', 'POST'])
def create_meal():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    error_message = None
    success_message = None
    
    if request.method == 'POST':
        meal_name = request.form.get('meal_name')
        food_items = []
        
        # Get all food items from form
        i = 0
        while True:
            food_name = request.form.get(f'food_name_{i}')
            food_quantity = request.form.get(f'food_quantity_{i}')
            if not food_name or not food_quantity:
                break
            food_items.append(f"{food_quantity} {food_name}")
            i += 1
        
        if meal_name and food_items:
            try:
                conn = sqlite3.connect('cedhealth.db')
                c = conn.cursor()
                
                # Create saved meal
                c.execute('''
                    INSERT INTO saved_meals (user_id, meal_name, created_date)
                    VALUES (?, ?, ?)
                ''', (session['user_id'], meal_name, datetime.now().date().isoformat()))
                
                saved_meal_id = c.lastrowid
                
                # Process each food item
                for food_item in food_items:
                    try:
                        response = requests.post(API_URL,
                                                 headers=HEADERS,
                                                 json={"query": food_item})
                        data = response.json()
                        
                        if 'foods' in data and data['foods']:
                            food = data['foods'][0]
                            
                            # Save food item to saved_meal_items
                            c.execute('''
                                INSERT INTO saved_meal_items (saved_meal_id, food_name, quantity, calories, protein, fat, carbs)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (saved_meal_id, food['food_name'], food_item,
                                  food['nf_calories'], food['nf_protein'],
                                  food['nf_total_fat'], food['nf_total_carbohydrate']))
                        else:
                            error_message = f"Nutrition data not found for: {food_item}"
                            break
                    except Exception as e:
                        error_message = f"Error processing '{food_item}': {str(e)}"
                        break
                
                if not error_message:
                    conn.commit()
                    success_message = f"Custom meal '{meal_name}' created successfully!"
                else:
                    # Delete the saved meal if there was an error
                    c.execute('DELETE FROM saved_meals WHERE id = ?', (saved_meal_id,))
                    conn.commit()
                
                conn.close()
                
            except Exception as e:
                error_message = f"Error creating meal: {str(e)}"
        else:
            error_message = "Please enter a meal name and at least one food item."
    
    return render_template('create_meal.html', 
                         error_message=error_message, 
                         success_message=success_message)


@app.route('/saved_meals')
def saved_meals():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('cedhealth.db')
    c = conn.cursor()
    
    # Get saved meals with their total nutrition
    c.execute('''
        SELECT sm.id, sm.meal_name, sm.created_date,
               SUM(smi.calories) as total_calories,
               SUM(smi.protein) as total_protein,
               SUM(smi.fat) as total_fat,
               SUM(smi.carbs) as total_carbs
        FROM saved_meals sm
        LEFT JOIN saved_meal_items smi ON sm.id = smi.saved_meal_id
        WHERE sm.user_id = ?
        GROUP BY sm.id, sm.meal_name, sm.created_date
        ORDER BY sm.created_date DESC
    ''', (session['user_id'],))
    
    saved_meals_data = c.fetchall()
    conn.close()
    
    return render_template('saved_meals.html', saved_meals=saved_meals_data)


@app.route('/log_saved_meal/<int:saved_meal_id>')
def log_saved_meal(saved_meal_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('cedhealth.db')
    c = conn.cursor()
    
    # Get saved meal items
    c.execute('''
        SELECT smi.food_name, smi.calories, smi.protein, smi.fat, smi.carbs
        FROM saved_meal_items smi
        JOIN saved_meals sm ON smi.saved_meal_id = sm.id
        WHERE sm.id = ? AND sm.user_id = ?
    ''', (saved_meal_id, session['user_id']))
    
    meal_items = c.fetchall()
    
    if meal_items:
        current_date = datetime.now().date().isoformat()
        
        # Log each item as a separate meal entry
        for item in meal_items:
            food_name, calories, protein, fat, carbs = item
            c.execute('''
                INSERT INTO meals (user_id, meal_name, calories, protein, fat, carbs, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (session['user_id'], food_name, calories, protein, fat, carbs, current_date))
        
        conn.commit()
    
    conn.close()
    return redirect(url_for('meals'))


# ---------- RUN ----------
if __name__ == '__main__':
    app.run(debug=True)