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
        CREATE TABLE IF NOT EXISTS daily_weights (
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
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS initial_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            weight REAL,
            weight_unit TEXT,
            height_cm INTEGER,
            height_ft INTEGER,
            height_in INTEGER,
            height_unit TEXT,
            target_weight REAL,
            target_date TEXT,
            goal_type TEXT,
            current_workout_frequency INTEGER,
            desired_workout_frequency INTEGER,
            workout_types TEXT,
            diet_preferences TEXT,
            motivation TEXT,
            tracking_preferences TEXT,
            created_date TEXT,
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


@app.route('/sw.js')
def service_worker():
    """Serve the service worker from the static directory"""
    from flask import send_from_directory
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')


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
        
        if user:
            session['user_id'] = user[0]
            session['username'] = username
            
            # Check if user has completed initial goals setup
            c.execute('SELECT id FROM initial_goals WHERE user_id = ?', (user[0],))
            initial_goals_complete = c.fetchone()
            
            conn.close()
            
            if not initial_goals_complete:
                return redirect(url_for('initial_goals'))
            else:
                return redirect(url_for('dashboard'))
        else:
            error = 'Invalid username or password'
            conn.close()
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
            user_id = c.lastrowid
            conn.commit()
            conn.close()
            
            # Auto-login and redirect to initial goals
            session['user_id'] = user_id
            session['username'] = username
            return redirect(url_for('initial_goals'))
        except sqlite3.IntegrityError:
            error = 'Username already exists.'
    return render_template('signup.html', error=error)


@app.route('/initial_goals', methods=['GET', 'POST'])
def initial_goals():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    error = None
    
    if request.method == 'POST':
        user_id = session['user_id']
        
        # Get form data
        weight = request.form.get('weight', type=float)
        weight_unit = request.form.get('weight_unit')
        height_cm = request.form.get('height_cm', type=int)
        height_ft = request.form.get('height_ft', type=int)
        height_in = request.form.get('height_in', type=int)
        height_unit = request.form.get('height_unit')
        target_weight = request.form.get('target_weight', type=float)
        target_date = request.form.get('target_date')
        goal_type = request.form.get('goal_type')
        current_workout_frequency = request.form.get('current_workout_frequency', type=int)
        desired_workout_frequency = request.form.get('desired_workout_frequency', type=int)
        
        # Get multi-select values
        workout_types = request.form.getlist('workout_types')
        diet_preferences = request.form.getlist('diet_preferences')
        tracking_preferences = request.form.getlist('tracking_preferences')
        
        motivation = request.form.get('motivation')
        
        # Basic validation
        if not weight or not goal_type or current_workout_frequency is None or desired_workout_frequency is None:
            error = 'Please fill in all required fields.'
        else:
            try:
                conn = sqlite3.connect('cedhealth.db')
                c = conn.cursor()
                
                # Save initial goals
                c.execute('''
                    INSERT INTO initial_goals (
                        user_id, weight, weight_unit, height_cm, height_ft, height_in, 
                        height_unit, target_weight, target_date, goal_type, 
                        current_workout_frequency, desired_workout_frequency, 
                        workout_types, diet_preferences, motivation, tracking_preferences, 
                        created_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id, weight, weight_unit, height_cm, height_ft, height_in,
                    height_unit, target_weight, target_date, goal_type,
                    current_workout_frequency, desired_workout_frequency,
                    ','.join(workout_types), ','.join(diet_preferences),
                    motivation, ','.join(tracking_preferences),
                    datetime.now().date().isoformat()
                ))
                
                # Calculate basic calorie and macro goals based on the input
                # This is a simplified calculation - you can make it more sophisticated
                base_calories = 2000  # Default starting point
                
                if goal_type == 'lose_weight':
                    calorie_goal = base_calories - 300
                    protein_goal = weight * 2.2 if weight_unit == 'kg' else weight * 1.0
                elif goal_type == 'gain_weight':
                    calorie_goal = base_calories + 300
                    protein_goal = weight * 2.5 if weight_unit == 'kg' else weight * 1.1
                else:  # maintain
                    calorie_goal = base_calories
                    protein_goal = weight * 2.0 if weight_unit == 'kg' else weight * 0.9
                
                # Set basic macro goals
                carbs_goal = calorie_goal * 0.4 / 4  # 40% of calories from carbs
                fat_goal = calorie_goal * 0.3 / 9    # 30% of calories from fat
                
                # Save to goals table
                c.execute('''
                    INSERT OR REPLACE INTO goals (
                        user_id, weight_goal, calorie_goal, protein_goal, carbs_goal, fat_goal
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    user_id, target_weight or weight, int(calorie_goal), 
                    round(protein_goal, 1), round(carbs_goal, 1), round(fat_goal, 1)
                ))
                
                conn.commit()
                conn.close()
                
                return redirect(url_for('dashboard'))
                
            except Exception as e:
                error = f'Error saving goals: {str(e)}'
    
    return render_template('initial_goals.html', username=session['username'], error=error)


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
    weight_goal = goal[0] if goal else None
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
        FROM daily_weights 
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
    
    # Get today's weight if logged
    c.execute('SELECT weight FROM daily_weights WHERE user_id = ? AND date = ?', (user_id, today))
    today_weight = c.fetchone()
    today_weight = today_weight[0] if today_weight else None
    
    # Calculate fiber (approximate: 3g per 100g carbs)
    current_fiber = round((current_carbs / 100) * 3, 1)

    # Calculate progress percentages
    protein_progress = min(100, (current_protein / protein_goal) * 100) if protein_goal > 0 else 0
    fat_progress = min(100, (current_fat / fat_goal) * 100) if fat_goal > 0 else 0
    carbs_progress = min(100, (current_carbs / carbs_goal) * 100) if carbs_goal > 0 else 0
    fiber_progress = min(100, (current_fiber / fiber_goal) * 100) if fiber_goal > 0 else 0

    # Get meal of the day
    recipe_data = None
    try:
        url = "https://api.spoonacular.com/recipes/random?number=1"
        headers = {"x-api-key": "669ab752fed34d5ea3f9b188b1983b8b"}
        
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if 'recipes' in data and data['recipes']:
            recipe = data['recipes'][0]
            from bs4 import BeautifulSoup
            summary = recipe.get('summary', '')
            if summary:
                soup = BeautifulSoup(summary, 'html.parser')
                summary = soup.get_text()
            
            recipe_data = {
                'title': recipe.get('title', 'Unknown Recipe'),
                'image': recipe.get('image', ''),
                'summary': summary[:200] + '...' if len(summary) > 200 else summary,
                'readyInMinutes': recipe.get('readyInMinutes', 0),
                'sourceUrl': recipe.get('sourceUrl', '')
            }
    except Exception as e:
        print(f"Error fetching meal of the day: {e}")

    # Get recommended diet summary
    diet_summary = None
    c.execute('''
        SELECT weight, weight_unit, goal_type, target_weight 
        FROM initial_goals 
        WHERE user_id = ? 
        ORDER BY created_date DESC 
        LIMIT 1
    ''', (user_id,))
    user_data = c.fetchone()
    
    if user_data:
        weight, weight_unit, goal_type, target_weight = user_data
        weight_lbs = weight * 2.20462 if weight_unit == 'kg' else weight
        
        if goal_type == 'gain_weight':
            calories_per_lb = 19
            protein_per_lb = 1.0
        elif goal_type == 'lose_weight':
            calories_per_lb = 13
            protein_per_lb = 1.2
        else:
            calories_per_lb = 15.5
            protein_per_lb = 1.0
        
        target_calories = int(weight_lbs * calories_per_lb)
        target_protein = int(weight_lbs * protein_per_lb)
        
        diet_summary = {
            'goal_type': goal_type,
            'target_calories': target_calories,
            'target_protein': target_protein
        }

    conn.close()

    return render_template('dashboard.html', 
                         username=session['username'],
                         daily_calories=daily_calories,
                         daily_weights=daily_weights,
                         weight_goal=weight_goal,
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
                         fiber_progress=round(fiber_progress, 1),
                         recipe_data=recipe_data,
                         diet_summary=diet_summary,
                         today_weight=today_weight,
                         today_date=today)


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
        # Try Nutritionix first
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
                    'photo': item.get('photo', {}).get('thumb', ''),
                    'source': 'nutritionix'
                })
        
        if 'branded' in data:
            for item in data['branded'][:5]:  # Limit to 5 items
                result['branded'].append({
                    'food_name': item['food_name'],
                    'brand_name': item.get('brand_name', ''),
                    'photo': item.get('photo', {}).get('thumb', ''),
                    'source': 'nutritionix'
                })
        
        # If Nutritionix returns no branded results, try Open Food Facts as fallback
        if not result['branded'] and len(result['common']) < 3:
            try:
                # Search Open Food Facts
                openfoodfacts_url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={query}&search_simple=1&action=process&json=1&page_size=5"
                openfoodfacts_response = requests.get(openfoodfacts_url, timeout=3)
                openfoodfacts_data = openfoodfacts_response.json()
                
                if 'products' in openfoodfacts_data:
                    for product in openfoodfacts_data['products'][:3]:  # Limit to 3 items
                        if product.get('product_name') and product.get('brands'):
                            result['branded'].append({
                                'food_name': product['product_name'],
                                'brand_name': product.get('brands', '').split(',')[0],  # Get first brand
                                'photo': product.get('image_thumb_url', ''),
                                'source': 'openfoodfacts'
                            })
            except:
                pass  # Ignore Open Food Facts errors, just use Nutritionix results
        
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
    analyze_results = []
    total_nutrition = {'calories': 0, 'protein': 0, 'fat': 0, 'carbs': 0, 'fiber': 0}

    # Handle adding new meal
    if request.method == 'POST' and request.form.get('action') == 'add_meal':
        quantity = request.form.get('quantity')
        unit = request.form.get('unit')
        food_name = request.form.get('food_name')

        if quantity and unit and food_name:
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

    # Handle meal analysis
    elif request.method == 'POST' and request.form.get('action') == 'analyze_meal':
        food_items = []
        i = 0
        while True:
            food_item = request.form.get(f'food_item_{i}')
            if not food_item:
                break
            food_items.append(food_item.strip())
            i += 1
        
        if food_items:
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
                        
                        analyze_results.append(food_nutrition)
                        
                        total_nutrition['calories'] += food_nutrition['calories']
                        total_nutrition['protein'] += food_nutrition['protein']
                        total_nutrition['fat'] += food_nutrition['fat']
                        total_nutrition['carbs'] += food_nutrition['carbs']
                        total_nutrition['fiber'] += food_nutrition['fiber']

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

    # Get meals for display
    date_filter = request.args.get('date')
    if not date_filter:
        date_filter = datetime.now().date().isoformat()
    
    user_id = session['user_id']
    conn = sqlite3.connect('cedhealth.db')
    c = conn.cursor()
    
    c.execute('SELECT * FROM meals WHERE user_id = ? AND date = ? ORDER BY id DESC',
              (user_id, date_filter))
    meals_by_user = c.fetchall()
    
    c.execute('SELECT SUM(protein), SUM(carbs), SUM(fat) FROM meals WHERE user_id = ? AND date = ?',
              (user_id, date_filter))
    macro_totals = c.fetchone()
    
    c.execute('SELECT protein_goal, carbs_goal, fat_goal FROM goals WHERE user_id = ?', (user_id,))
    macro_goals = c.fetchone()
    
    # Get saved meals
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
    ''', (user_id,))
    
    saved_meals_data = c.fetchall()
    conn.close()

    return render_template('meals.html',
                           meals=meals_by_user,
                           selected_date=date_filter,
                           nutrition_data=nutrition_data,
                           error_message=error_message,
                           macro_totals=macro_totals,
                           macro_goals=macro_goals,
                           current_date=datetime.now().date().isoformat(),
                           saved_meals=saved_meals_data,
                           analyze_results=analyze_results,
                           total_nutrition=total_nutrition)


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
    if weight and 50 <= weight <= 999:  # Basic validation
        conn = sqlite3.connect('cedhealth.db')
        c = conn.cursor()
        
        # Use INSERT OR REPLACE for upsert functionality
        today = datetime.now().date().isoformat()
        user_id = session['user_id']
        
        # Check if record exists for today
        c.execute('SELECT id FROM daily_weights WHERE user_id = ? AND date = ?', (user_id, today))
        existing = c.fetchone()
        
        if existing:
            # Update existing record
            c.execute('UPDATE daily_weights SET weight = ? WHERE user_id = ? AND date = ?',
                      (weight, user_id, today))
        else:
            # Insert new record
            c.execute('INSERT INTO daily_weights (user_id, weight, date) VALUES (?, ?, ?)',
                      (user_id, weight, today))
        
        # Also update the old weight_logs table for backward compatibility
        c.execute('DELETE FROM weight_logs WHERE user_id = ? AND date = ?', (user_id, today))
        c.execute('INSERT INTO weight_logs (user_id, weight, date) VALUES (?, ?, ?)',
                  (user_id, weight, today))
        
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
        
        # Log each item as a separate meal entry with today's date
        for item in meal_items:
            food_name, calories, protein, fat, carbs = item
            c.execute('''
                INSERT INTO meals (user_id, meal_name, calories, protein, fat, carbs, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (session['user_id'], food_name, calories, protein, fat, carbs, current_date))
        
        conn.commit()
    
    conn.close()
    return redirect(url_for('meals'))


@app.route('/explore_foods', methods=['GET', 'POST'])
def explore_foods():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    error_message = None
    product_info = None
    food_nutrition = None
    
    # Handle barcode scanning
    if request.method == 'POST' and request.form.get('action') == 'scan_barcode':
        barcode = request.form.get('barcode', '').strip()
        
        if not barcode:
            error_message = "Please enter a barcode."
        else:
            try:
                url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
                response = requests.get(url)
                data = response.json()
                
                if data.get('status') == 1 and 'product' in data:
                    product = data['product']
                    
                    product_info = {
                        'name': product.get('product_name', 'Unknown Product'),
                        'brand': product.get('brands', 'Unknown Brand'),
                        'calories': product.get('nutriments', {}).get('energy-kcal_100g', 0),
                        'protein': product.get('nutriments', {}).get('proteins_100g', 0),
                        'fat': product.get('nutriments', {}).get('fat_100g', 0),
                        'carbs': product.get('nutriments', {}).get('carbohydrates_100g', 0),
                        'barcode': barcode,
                        'image_url': product.get('image_url', '')
                    }
                else:
                    error_message = f"Product with barcode {barcode} not found in the database."
                    
            except Exception as e:
                error_message = f"Error fetching product data: {str(e)}"
    
    # Handle food lookup
    elif request.method == 'POST' and request.form.get('action') == 'lookup_food':
        food_query = request.form.get('food_query', '').strip()
        
        if not food_query:
            error_message = "Please enter a food name."
        else:
            try:
                response = requests.post(API_URL,
                                         headers=HEADERS,
                                         json={"query": food_query})
                data = response.json()
                
                if 'foods' in data and data['foods']:
                    food = data['foods'][0]
                    food_nutrition = {
                        'name': food['food_name'],
                        'calories': food['nf_calories'],
                        'protein': food['nf_protein'],
                        'fat': food['nf_total_fat'],
                        'carbs': food['nf_total_carbohydrate'],
                        'fiber': food.get('nf_dietary_fiber', 0),
                        'sugar': food.get('nf_sugars', 0),
                        'sodium': food.get('nf_sodium', 0)
                    }
                else:
                    error_message = "Nutrition data not found for the provided food."
            except Exception as e:
                error_message = f"Error fetching nutrition data: {str(e)}"
    
    return render_template('explore_foods.html', 
                         error_message=error_message, 
                         product_info=product_info,
                         food_nutrition=food_nutrition)


@app.route('/workouts')
def workouts():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    exercises_data = []
    gif_exercises_data = []
    categories_data = []
    error_message = None
    selected_category = request.args.get('category', '')
    
    try:
        # Fetch exercise categories
        categories_url = "https://wger.de/api/v2/exercisecategory/"
        categories_response = requests.get(categories_url)
        categories_json = categories_response.json()
        
        if 'results' in categories_json:
            for category in categories_json['results']:
                categories_data.append({
                    'id': category.get('id'),
                    'name': category.get('name', 'Unknown Category')
                })
        
        # Fetch regular exercises
        exercises_url = "https://wger.de/api/v2/exercise/?language=2&limit=10"
        if selected_category:
            exercises_url += f"&category={selected_category}"
            
        exercises_response = requests.get(exercises_url)
        exercises_json = exercises_response.json()
        
        if 'results' in exercises_json:
            for exercise in exercises_json['results']:
                exercise_data = {
                    'name': exercise.get('name', 'Unknown Exercise'),
                    'description': exercise.get('description', 'No description available'),
                    'category': exercise.get('category', 'Unknown Category')
                }
                exercises_data.append(exercise_data)
        
        # Fetch GIF exercises from ExerciseDB
        gif_url = "https://exercisedb.p.rapidapi.com/exercises?limit=8"
        gif_headers = {
            "x-rapidapi-key": "e5ab48f2b8msh50c42a50dce5e64p1592edjsn1ad068fbd807",
            "x-rapidapi-host": "exercisedb.p.rapidapi.com"
        }
        
        gif_response = requests.get(gif_url, headers=gif_headers)
        gif_response.raise_for_status()
        
        gif_exercises_json = gif_response.json()
        
        if isinstance(gif_exercises_json, list):
            for exercise in gif_exercises_json:
                if isinstance(exercise, dict):
                    exercise_data = {
                        'name': exercise.get('name', 'Unknown Exercise'),
                        'bodyPart': exercise.get('bodyPart', 'Unknown Body Part'),
                        'equipment': exercise.get('equipment', 'Unknown Equipment'),
                        'target': exercise.get('target', 'Unknown Target'),
                        'gifUrl': exercise.get('gifUrl', '')
                    }
                    gif_exercises_data.append(exercise_data)
    
    except Exception as e:
        error_message = f"Error fetching exercises: {str(e)}"
    
    return render_template('workouts.html', 
                         exercises=exercises_data,
                         gif_exercises=gif_exercises_data,
                         categories=categories_data,
                         selected_category=selected_category,
                         error_message=error_message)


@app.route('/gif_exercises')
def gif_exercises():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    exercises_data = []
    error_message = None
    
    try:
        # Fetch exercises from ExerciseDB API via RapidAPI
        url = "https://exercisedb.p.rapidapi.com/exercises?limit=12"
        headers = {
            "x-rapidapi-key": "e5ab48f2b8msh50c42a50dce5e64p1592edjsn1ad068fbd807",
            "x-rapidapi-host": "exercisedb.p.rapidapi.com"
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        exercises_json = response.json()
        
        # Check if response is a list (expected format from ExerciseDB)
        if isinstance(exercises_json, list):
            # Process exercises
            for exercise in exercises_json:
                if isinstance(exercise, dict):
                    exercise_data = {
                        'name': exercise.get('name', 'Unknown Exercise'),
                        'bodyPart': exercise.get('bodyPart', 'Unknown Body Part'),
                        'equipment': exercise.get('equipment', 'Unknown Equipment'),
                        'target': exercise.get('target', 'Unknown Target'),
                        'gifUrl': exercise.get('gifUrl', '')
                    }
                    exercises_data.append(exercise_data)
        else:
            error_message = "Unexpected response format from ExerciseDB API"
    
    except requests.exceptions.RequestException as e:
        error_message = f"Network error fetching exercises: {str(e)}"
    except ValueError as e:
        error_message = f"Error parsing exercise data: {str(e)}"
    except Exception as e:
        error_message = f"Error fetching exercises: {str(e)}"
    
    return render_template('gif_exercises.html', exercises=exercises_data, error_message=error_message)


@app.route('/meal_of_the_day')
def meal_of_the_day():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    recipe_data = None
    error_message = None
    
    try:
        # Fetch random recipe from Spoonacular API
        url = "https://api.spoonacular.com/recipes/random?number=1"
        headers = {"x-api-key": "669ab752fed34d5ea3f9b188b1983b8b"}
        
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if 'recipes' in data and data['recipes']:
            recipe = data['recipes'][0]
            
            # Clean HTML from summary using BeautifulSoup
            from bs4 import BeautifulSoup
            summary = recipe.get('summary', '')
            if summary:
                soup = BeautifulSoup(summary, 'html.parser')
                summary = soup.get_text()
            
            recipe_data = {
                'title': recipe.get('title', 'Unknown Recipe'),
                'image': recipe.get('image', ''),
                'summary': summary,
                'readyInMinutes': recipe.get('readyInMinutes', 0),
                'sourceUrl': recipe.get('sourceUrl', '')
            }
        else:
            error_message = "No recipe found. Please try again."
            
    except Exception as e:
        error_message = f"Error fetching recipe: {str(e)}"
    
    return render_template('meal_of_the_day.html', recipe=recipe_data, error_message=error_message)


@app.route('/recommended_diet')
def recommended_diet():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = sqlite3.connect('cedhealth.db')
    c = conn.cursor()
    
    # Get user's initial goals and current weight
    c.execute('''
        SELECT weight, weight_unit, goal_type, target_weight 
        FROM initial_goals 
        WHERE user_id = ? 
        ORDER BY created_date DESC 
        LIMIT 1
    ''', (user_id,))
    user_data = c.fetchone()
    conn.close()
    
    if not user_data:
        return render_template('recommended_diet.html', 
                             error_message="Please complete your initial goals setup first.",
                             meal_plan=None, macros=None)
    
    weight, weight_unit, goal_type, target_weight = user_data
    
    # Convert weight to lbs if needed
    weight_lbs = weight * 2.20462 if weight_unit == 'kg' else weight
    
    # Calculate macros based on goal
    if goal_type == 'gain_weight':  # Bulk
        calories_per_lb = 19  # Average of 18-20
        protein_per_lb = 1.0
        fat_per_lb = 0.4
    elif goal_type == 'lose_weight':  # Cut
        calories_per_lb = 13  # Average of 12-14
        protein_per_lb = 1.2
        fat_per_lb = 0.3  # Conservative estimate
    else:  # Maintain
        calories_per_lb = 15.5  # Average of 15-16
        protein_per_lb = 1.0
        fat_per_lb = 0.35  # Conservative estimate
    
    # Calculate daily targets
    target_calories = int(weight_lbs * calories_per_lb)
    target_protein = int(weight_lbs * protein_per_lb)
    target_fat = int(weight_lbs * fat_per_lb)
    
    # Calculate carbs (rest of calories after protein and fat)
    protein_calories = target_protein * 4
    fat_calories = target_fat * 9
    carb_calories = target_calories - protein_calories - fat_calories
    target_carbs = int(carb_calories / 4)
    
    macros = {
        'calories': target_calories,
        'protein': target_protein,
        'fat': target_fat,
        'carbs': target_carbs,
        'goal_type': goal_type
    }
    
    # Get meal plan from Spoonacular
    meal_plan = None
    error_message = None
    
    try:
        # Call Spoonacular meal planner API
        url = "https://api.spoonacular.com/mealplanner/generate"
        params = {
            'timeFrame': 'day',
            'targetCalories': target_calories,
            'apiKey': '669ab752fed34d5ea3f9b188b1983b8b'
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if 'meals' in data:
            meal_plan = []
            for meal in data['meals']:
                meal_info = {
                    'id': meal.get('id'),
                    'title': meal.get('title', 'Unknown Meal'),
                    'readyInMinutes': meal.get('readyInMinutes', 0),
                    'servings': meal.get('servings', 1),
                    'sourceUrl': meal.get('sourceUrl', ''),
                    'image': f"https://spoonacular.com/recipeImages/{meal.get('id')}-312x231.jpg" if meal.get('id') else ''
                }
                meal_plan.append(meal_info)
        else:
            error_message = "Could not generate meal plan. Please try again."
            
    except Exception as e:
        error_message = f"Error fetching meal plan: {str(e)}"
    
    return render_template('recommended_diet.html', 
                         macros=macros, 
                         meal_plan=meal_plan, 
                         error_message=error_message)


# ---------- RUN ----------
if __name__ == '__main__':
    import os
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)