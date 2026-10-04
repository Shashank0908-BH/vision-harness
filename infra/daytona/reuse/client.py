"""Deploy/start/status/pull for the registered workspace; creates no cloud resources."""

import argparse
import hashlib
import json
import shlex
import tarfile

from dotenv import dotenv_values

from infra.daytona.manage import ROOT, client, owned
from infra.daytona.reuse.common import LOCAL, NAME, REMOTE


def checked(box, command, **kwargs):
    result = box.process.exec(command, **kwargs)
    if result.exit_code:
        raise RuntimeError(result.result[-4000:])
    return result.result


def deploy(box):
    archive = LOCAL.with_suffix(".tar.gz")
    remote_archive = f"/tmp/{NAME}.tar.gz"
    box.fs.upload_file(str(archive), remote_archive, timeout=60)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    command = (f"test ! -e {shlex.quote(str(REMOTE))} && mkdir -p /root/vision-benchmarks "
        f"&& echo '{digest}  {remote_archive}' | sha256sum -c - "
        f"&& tar -xzf {shlex.quote(remote_archive)} -C /root/vision-benchmarks "
        f"&& mkdir -p /persist/artifacts/{NAME} "
        f"&& cp {shlex.quote(remote_archive)} /persist/artifacts/{NAME}/frozen-inputs.tar.gz "
        f"&& rm {shlex.quote(remote_archive)}")
    print(checked(box, command, timeout=120))


def start(box):
    # Secrets travel only through the SDK env argument, never argv/files/images.
    values = dotenv_values(ROOT / ".env")
    env = {k: v for k, v in values.items() if k in ("OPENAI_API_KEY", "JEV_API_KEY", "TYPESAFE_API_KEY") and v}
    if not env.get("OPENAI_API_KEY") or not (env.get("JEV_API_KEY") or env.get("TYPESAFE_API_KEY")):
        raise ValueError("Provider keys missing")
    script = f'''import json,os,pathlib,subprocess
r=pathlib.Path({str(REMOTE)!r})
marker=r/'coordinator.json'
if marker.exists(): raise RuntimeError('Coordinator already launched; inspect status, do not duplicate')
os.environ['PYTHONPATH']=str(r/'frozen/src')+':'+str(r/'frozen')
os.environ['PYTHONDONTWRITEBYTECODE']='1'
subprocess.run(['/opt/venvs/science/bin/python','-m','infra.daytona.reuse.health','--output',str(r/'providers-health.json')],cwd=r/'frozen',check=True)
with (r/'coordinator.log').open('ab') as log:
 p=subprocess.Popen(['/opt/venvs/science/bin/python','-u','-m','infra.daytona.reuse.runner',str(r)],cwd=r/'frozen',stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
 marker.write_text(json.dumps({{'pid':p.pid,'workspace_id':{box.id!r}}}))
print(marker.read_text())
'''
    print(checked(box, "/opt/venvs/science/bin/python -c " + shlex.quote(script), env=env, timeout=120))


def status(box):
    command = f"cat {shlex.quote(str(REMOTE / 'status.json'))}; tail -n 18 {shlex.quote(str(REMOTE / 'coordinator.log'))}"
    print(checked(box, command, timeout=30))


def pull(box):
    remote = f"/tmp/{NAME}-results.tar.gz"
    # Source/input labels stay frozen locally; sync only outputs and metadata.
    command = (f"tar -czf {shlex.quote(remote)} -C {shlex.quote(str(REMOTE))} "
        "jobs reports status.json coordinator.json coordinator.log checkpointed.json")
    checked(box, command, timeout=120)
    archive = LOCAL / "results-download.tar.gz"
    # SDK 0.216 accepts this overload's timeout positionally only.
    box.fs.download_file(remote, str(archive), 120)
    with tarfile.open(archive) as bundle:
        bundle.extractall(LOCAL, filter="data")
    checked(box, "rm " + shlex.quote(remote), timeout=15)
    print(json.dumps({"downloaded": str(LOCAL), "bytes": archive.stat().st_size}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["deploy", "start", "status", "pull"])
    args = parser.parse_args()
    box = owned(client())
    globals()[args.action](box)
