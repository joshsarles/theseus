# How to setup host for remote access
## Verify MLflow is binding to 0.0.0.0
Already set in your compose, so that's covered:
```bash
--host 0.0.0.0
```
## Get the host machine's LAN IP
```bash
ip -4 addr show | grep inet
# or
hostname -I
```