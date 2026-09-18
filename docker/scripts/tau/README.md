# Tau Connection Visualizer on WET Server

Open **http://YOUR-SERVER:9999/tau** after installing the app.
If WET is behind an HTTPS reverse proxy, use its usual base URL followed by /tau.

## Install on the existing server

From the wet_server checkout, after merging the Tau pull request:

```sh
git pull --ff-only origin master
sudo mkdir -p /home/wet_model/scripts/tau
sudo cp docker/scripts/tau/main.py docker/scripts/tau/tau_engine.py docker/scripts/tau/tau_model.py docker/scripts/tau/index.html /home/wet_model/scripts/tau/
curl -f http://127.0.0.1:9999/tau -o /dev/null
```

The repository provisioning mounts /home/wet_model/scripts onto /app/scripts.
That mount hides apps bundled in the image, so pulling a new Docker image alone
does not install this app. For a custom mount, copy into its corresponding scripts folder.
No extra packages or separate port are needed. First installation loads on request.
When replacing an already-loaded Tau engine, restart wet_app to refresh worker imports.

## Preview the contribution before merging

Fetch and check out feat/tau-visualizer in a separate checkout, then use the same
mkdir/cp/curl commands above (omit the master pull).

## Use

Drag nodes, edit energy/capacity and connections, then Play or Step through F/D/V/H.
Save and Load transfer lattice JSON through the browser. Each request carries its
own state; there is no shared server-side simulation or persistent saved world.
Save JSON before refreshing. See MODEL.md for mathematical assumptions and limits;
its standalone launch commands refer to the original desktop experiment.

## Verify

With the repository's Flask dependencies installed:

```sh
python -B -m unittest discover -s tests -p 'test_tau_*.py' -v
```
