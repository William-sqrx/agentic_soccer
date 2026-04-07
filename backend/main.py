import argparse
import os
from app import app

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    if args.debug:
        os.environ["DEBUG_MODE"] = "true"

    app.run(host="0.0.0.0", port=8000, debug=args.debug)

if __name__ == "__main__":
    main()
