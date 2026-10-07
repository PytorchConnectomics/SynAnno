import logging
import os

from dotenv import load_dotenv

from synanno import create_app

# TODO: Have a look at urllib3.connectionpool:Connection pool is full
logging.getLogger("urllib3").setLevel(logging.ERROR)

load_dotenv()  # Load environment variables from .env

# Initialize the app using the factory function
app = create_app()


if __name__ == "__main__":
    # The dev server binds to localhost and runs without the debugger unless asked
    app.run(
        host=os.getenv("APP_IP", "127.0.0.1"),
        port=app.config["PORT"],
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )
