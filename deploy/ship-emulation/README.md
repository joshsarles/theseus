# USS Theseus (DDG-118) — destroyer-as-containers emulation

This deployment models the destroyer **USS Theseus (DDG-118)** as a set of
**independent subsystems, each running in its own container**. It is the
ship-scale analog of `deploy/pi-emulation/` (which emulated two physical Raspberry
Pi UUV nodes). Here there is no hardware at all — every subsystem is a container
on the Mac, wired to the same Mac-host MLflow registry.

## The story

A real destroyer is not one computer. It is a federation of subsystems — the
engineering plant, the propulsion train, the auxiliaries, the sonar suite, the
combat/C2 system, the navigation stack — each with its own controllers, its own
sensor channels, and its own failure modes. Each subsystem watches *itself*.

We mirror that exactly:

- **One container per subsystem.** Six nodes, each an isolated process with its
  own port and its own anomaly model.
- **Every node reuses the same `analytics:latest` image** — the FastAPI receiver.
  The subsystems differ only by the config they mount and the model that config
  names. (Same trick as the Pi fleet: one image, many roles.)
- **Each node loads its OWN model** from the shared Mac-host MLflow registry on
  `:5050` via `host.docker.internal`. The model for subsystem `<key>` is registered
  as `<key>_deploy` (e.g. `sonar_deploy`).
- **All six share a `ship` bridge network** — the destroyer's internal data bus.
- **Each exposes a distinct host port** so you can poke any subsystem individually.

```
                 host.docker.internal:5050  (Mac-host MLflow registry)
                          ▲   loads <key>_deploy
        ┌─────────────────┼─────────────────┐
   ship bridge network (the ship's internal data bus)
   ┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
 machinery  propulsion  auxiliary    sonar       c2          nav
 :54541      :54542      :54543      :54544      :54545      :54546
   each = analytics:latest + its own /cfg/config.yml
```

## Node → port → model

| Subsystem  | Container            | Host port | Mounted config            | Registered model    |
|------------|----------------------|-----------|---------------------------|---------------------|
| MACHINERY  | `theseus-machinery`  | 54541     | `config.machinery.yml`    | `machinery_deploy`  |
| PROPULSION | `theseus-propulsion` | 54542     | `config.propulsion.yml`   | `propulsion_deploy` |
| AUXILIARY  | `theseus-auxiliary`  | 54543     | `config.auxiliary.yml`    | `auxiliary_deploy`  |
| SONAR      | `theseus-sonar`      | 54544     | `config.sonar.yml`        | `sonar_deploy`      |
| C2         | `theseus-c2`         | 54545     | `config.c2.yml`           | `c2_deploy`         |
| NAV        | `theseus-nav`        | 54546     | `config.nav.yml`          | `nav_deploy`        |

All six map host port → container `:54321` (the receiver's listen port).

## The receiver recipe (identical to the Pi fleet)

Every node sets the same four conditions proven on the real Pis:

1. `RECEIVER_CONFIG=/cfg/config.yml` — the per-subsystem config, bind-mounted read-only.
2. `MLFLOW_TRACKING_URI=http://host.docker.internal:5050` — proxied artifact download.
3. `extra_hosts: host.docker.internal:host-gateway` — reach the Mac host from the container.
4. `image: analytics:latest` — the byte-identical receiver image.

The compose file keeps this DRY with a single `x-subsystem` YAML anchor; each
service only overrides `container_name`, `hostname`, `ports`, `NODE_ID`, and the
mounted config.

## Quick start

```bash
bash deploy/ship-emulation/up.sh                       # bring all 6 subsystems up + verify
bash deploy/ship-emulation/up.sh --feed                # + synthetic feed (1 rec/30s each)
bash deploy/ship-emulation/up.sh --feed --interval=2   # livelier feed for a live demo
bash deploy/ship-emulation/up.sh --feed --replay       # feed the REALISTIC labeled UUV streams
bash deploy/ship-emulation/down.sh                     # tear down (+ stop feeders)
```

`up.sh` will tag `localhost/analytics:latest -> analytics:latest` if needed, start
the Mac-host MLflow on `:5050` if it's down, `docker compose up -d`, then poll each
node's `/health` until it has loaded its model.

> The **model lane** registers the six `<key>_deploy` models into MLflow in
> parallel. Until a subsystem's model exists in the registry, that node will start
> but its `/health` may stay unready — that's expected; it becomes healthy once its
> model is registered. The compose stack itself is valid and ready to `up` now.

## Feeder options

- **Synthetic (default `--feed`)** — `serve/receiver/gen_synthetic_sensors.py --stream
  --url …` POSTs one generated record per `--interval` into each node's `/stream-item`.
- **Realistic replay (`--feed --replay`)** — replays the **labeled UUV json streams**
  under `serve/receiver/data/` (the realistic anomaly-tagged corpus) record-by-record
  into each node. Per-subsystem source mapping (closest available analog):
  - MACHINERY / PROPULSION / NAV ← `uuv1-telemetry-anom.json`
  - AUXILIARY ← `uuv1-all-anom.json`
  - SONAR ← `uuv1-sensors-anom.json`
  - C2 ← `uuv1-c2-anom.json`

Feeder logs land in `deploy/ship-emulation/.feed-<port>.log`.

## Probing a subsystem

```bash
curl -fsS http://127.0.0.1:54544/health     # SONAR ready + model loaded?
curl -fsS http://127.0.0.1:54544/history    # recent scored records
curl -fsS -X POST http://127.0.0.1:54544/stream-item -H 'Content-Type: application/json' -d '{...}'
```

## Files

- `docker-compose.yml` — 6 subsystem services, DRY via the `x-subsystem` anchor, `ship` bridge net.
- `config.<key>.yml` — per-subsystem receiver config pointing at `<key>_deploy` and `:5050`.
- `up.sh` / `down.sh` — one-command bring-up (with optional feed/replay) and teardown.
