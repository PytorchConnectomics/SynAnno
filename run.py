from synanno import configure_app

app = configure_app()

if __name__ == "__main__":
    app.run(host=app.config["IP"], port=app.config["PORT"])
