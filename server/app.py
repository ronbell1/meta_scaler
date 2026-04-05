from openenv.core.env_server.http_server import create_app
from .environment import LegalContractEnv

try:
    # Primary path: CWD-based execution (uv run server / uvicorn server.app:app)
    from models import Action, Observation
except ImportError:
    # Fallback: installed as sub-package of a larger project
    from ..models import Action, Observation


app = create_app(
    LegalContractEnv,
    Action,
    Observation,
    env_name="legal-contract-review",
    max_concurrent_envs=1,
)


def main(host: str = "0.0.0.0", port: int = 7860) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    main(port=args.port)
