"""Isolated loopback replay service; no live-feed or broker endpoint."""
import argparse
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

from .categorical_sac import CategoricalSAC


class ReplayRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    recipe_identity: str
    columns: list[str]
    window: list[list[float]]


def create_app(policy):
    app = FastAPI(title='Pinned categorical SAC replay provider')

    @app.get('/health')
    def health():
        return dict(state='MODEL_LOADED', live_ready=False, execution_authorized=False)

    @app.get('/v1/model')
    def model():
        return policy.info()

    @app.post('/v1/replay')
    def replay(request: ReplayRequest):
        try:
            return policy.replay(request.recipe_identity, request.columns, request.window)
        except (ValueError, TypeError, OverflowError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8769)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    policy = CategoricalSAC(**config)
    import uvicorn
    uvicorn.run(create_app(policy), host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
