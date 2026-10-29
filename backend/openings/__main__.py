import argparse
import os

import uvicorn

from .app import create_app


def main():
    parser = argparse.ArgumentParser(description="Run the Openings workspace.")
    parser.add_argument("--host", default=os.environ.get("OPENINGS_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("OPENINGS_PORT", "8080")))
    parser.add_argument(
        "--database", default=os.environ.get("OPENINGS_DATABASE", "data/openings.sqlite")
    )
    args = parser.parse_args()
    uvicorn.run(create_app(args.database), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
