# How to setup client for remote access
## Update the Pi's client .env
```bash
MLFLOW_SERVER_HOST=192.168.x.x   # your host machine's LAN IP
MLFLOW_SERVER_PORT=5000
```
No changes needed to the server compose file.

Firewall — most likely culprit if it doesn't connect
```bash
# Check if port 5000 is blocked on the server machine
sudo ufw status

## Open it if needed
sudo ufw allow 5000/tcp
```

For firewalld (RHEL/Fedora):
```bash
sudo firewall-cmd --add-port=5000/tcp --permanent
sudo firewall-cmd --reload
```

## Verify connectivity from the Pi before running containers
```bash
# Confirm the port is reachable
curl http://192.168.x.x:5000/health

#Should return: {"status": "OK"}
```