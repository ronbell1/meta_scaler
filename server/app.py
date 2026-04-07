from openenv.core.env_server.http_server import create_app
from .environment import ProcurementAuditEnv

try:
    from models import Action, Observation
except ImportError:
    from ..models import Action, Observation


app = create_app(
    ProcurementAuditEnv,
    Action,
    Observation,
    env_name="procurement-contract-audit",
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
