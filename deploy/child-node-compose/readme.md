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


## k3s / calico setup

sudo sed -i '$ s/$/ cgroup_memory=1 cgroup_enable=memory/' /boot/firmware/cmdline.txt

sudo reboot

curl -LO "https://k8s.io(curl -L -s https://k8s.io)/bin/linux/arm64/kubectl"

sudo mv kubectl /usr/local/bin/

curl -sfL https://get.k3s.io | sh -s - \
  --flannel-backend=none \
  --disable-network-policy \
  --disable=traefik \          # don't conflict with istio ingress
  --write-kubeconfig-mode=644

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

sudo k3s kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.27.0/manifests/calico.yaml

sudo k3s kubectl wait --for=condition=ready pod \
  -l k8s-app=calico-node \
  -n kube-system \
  --timeout=120s

k3s kubectl get pods -n kube-system -l k8s-app=calico-node