import argparse

parser = argparse.ArgumentParser()
parser.add_argument("phase", choices=["prepare", "infer", "score", "report"])
args = parser.parse_args()
if args.phase == "prepare":
    from .data import prepare
    prepare()
elif args.phase == "infer":
    from .runner import infer
    infer()
elif args.phase == "score":
    from .metrics import score
    score()
else:
    from .report import render
    render()
