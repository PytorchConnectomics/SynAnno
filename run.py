from synanno import create_app
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

# Initialize the app using the factory function
app = create_app()

if __name__ == "__main__":
    app.run(host=app.config["IP"], port=app.config["PORT"], debug=True)
