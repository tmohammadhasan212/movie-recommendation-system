from pathlib import Path

from backend.ml.train import train_model

ROOT = Path(__file__).resolve().parents[2]


if __name__ == "__main__":
    artifact = train_model(ROOT / "data" / "ml-latest-small", ROOT / "models")
    print(artifact)
