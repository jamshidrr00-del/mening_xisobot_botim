from flask import Flask, render_template

app = Flask(__name__)

# Bosh sahifani ko'rsatish uchun yo'l
@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    # Serverni ishga tushirish
    app.run(host='0.0.0.0', port=5000)
