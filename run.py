import logging

from dotenv import load_dotenv

from synanno import create_app

# TODO: Have a look at urllib3.connectionpool:Connection pool is full
logging.getLogger("urllib3").setLevel(logging.ERROR)

load_dotenv()  # Load environment variables from .env

# Initialize the app using the factory function
app = create_app()


if __name__ == "__main__":
    app.run(host=app.config["IP"], port=app.config["PORT"], debug=True)
