from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev")

@app.route('/')
def home():
    meal_name = "Chicken & Rice Bowl"
    meal_calories = 610
    meal_protein = 45

    if 'user_id' in session:
        user_id = session['user_id']
        conn = sqlite3.connect('cedhealth.db')
        c = conn.cursor()
        c.execute('SELECT weight_goal, calorie_goal FROM goals WHERE user_id = ?', (user_id,))
        goal = c.fetchone() or (0, 0)

        c.execute('SELECT COUNT(*) FROM meals WHERE user_id = ?', (user_id,))
        total_meals = c.fetchone()[0]
        conn.close()

        return render_template('home.html',
                               weight_goal=goal[0],
                               calorie_goal=goal[1],
                               total_meals=total_meals,
                               meal_name=meal_name,
                               meal_calories=meal_calories,
                               meal_protein=meal_protein)
    else:
        return render_template('home.html',
                               meal_name=meal_name,
                               meal_calories=meal_calories,
                               meal_protein=meal_protein)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=81)
