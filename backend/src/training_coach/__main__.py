"""Entry point: ``python -m training_coach`` or the ``training-coach`` script."""

import uvicorn

from training_coach.api.app import create_app
from training_coach.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        create_app(settings),
        host="0.0.0.0",  # noqa: S104 - bound inside the container; only the tunnel reaches it
        port=8080,
        log_config=None,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
