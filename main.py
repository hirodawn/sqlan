import logging
import sys
import tomllib
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

def load_config(path: str) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)

if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.toml"
    config = load_config(config_path)
    from web.app import create_app
    app = create_app(config)
    uvicorn.run(app, host="0.0.0.0", port=8000)
