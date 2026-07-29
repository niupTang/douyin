import os
from pathlib import Path

from conf import BASE_DIR
from koubo_integration import KouboStore, create_koubo_blueprint, register_realtime
from sau_backend import app


app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024
koubo_store = KouboStore(Path(BASE_DIR / "db" / "database.db"))
koubo_store.initialize()
app.register_blueprint(
    create_koubo_blueprint(
        koubo_store,
        Path(BASE_DIR / "koubo_data"),
        os.environ.get("KOUBO_ADMIN_TOKEN"),
    )
)
register_realtime(app, koubo_store)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5409)
