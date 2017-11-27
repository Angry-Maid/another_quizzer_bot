import os
import sqlite3


if not os.path.exists("questions.sqlite3"):
    open('questions.sqlite3', 'a+').close()

db = sqlite3.connect('questions.sqlite3').execute("CREATE TABLE IF NOT EXISTS questions (id INTEGER UNIQUE, category TEXT, question TEXT, answer TEXT, answers TEXT, has_file INTEGER, is_button INTEGER)").close()
