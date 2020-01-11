import hydra
import logging
import sys
import argparse
from pathlib import Path

from calbert import tokenizer

log = logging.getLogger(__name__)

TASK_WITH_ARGS = (None, None)

VALID_COMMANDS = ["tokenizer"]

TASKS = {"tokenizer": tokenizer.train}
PARSERS = {"tokenizer": tokenizer.arguments}


def parse(command):
    parser = PARSERS[command]()
    parser.add_argument("override", nargs="*", help="config overrides")
    args = parser.parse_args()
    override = args.override
    del args.override
    return args, override


@hydra.main(config_path="config.yaml", strict=True)
def main(cfg):
    task, args = TASK_WITH_ARGS
    task(args, cfg)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd not in VALID_COMMANDS:
        log.error(f"Invalid command {cmd}: must be one {', '.join(VALID_COMMANDS)}")
        exit(-1)
    del sys.argv[1]
    args, override = parse(cmd)
    sys.argv = [sys.argv[0]] + override
    TASK_WITH_ARGS = (TASKS[cmd], args)
    main()
