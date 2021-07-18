#!/usr/bin/env bash

set -eux

git clean -xid
./scripts/build_site.sh

git clone git@gitlab.com:multiprocessio/datastation workspace || true
( cd workspace && git pull && yarn && yarn build-ui )

echo "
<script async src=\"https://www.googletagmanager.com/gtag/js?id=G-0YH69RMKWK\"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', 'G-0YH69RMKWK');
</script>" >> workspace/build/index.html

REMOTE=fedora@datastation.multiprocess.io
REMOTE_HOME=/home/fedora

function remote_copy () {
    rsync -r --delete-after $1 $REMOTE:$2
}

function remote_run () {
    ssh $REMOTE -- "$1"
}

remote_run "sudo dnf install rsync"
remote_copy "workspace/build/*" $REMOTE_HOME/ui
remote_copy "build/*" $REMOTE_HOME/site
remote_copy scripts/setup_tls.sh $REMOTE_HOME/setup_tls.sh
remote_copy config/nginx.conf $REMOTE_HOME/nginx.conf
remote_copy config/selinux.conf $REMOTE_HOME/selinux.conf
remote_run "sudo dnf install -y nginx && sudo systemctl enable nginx && sudo firewall-cmd --add-service=http && sudo firewall-cmd --add-service=https && sudo service firewalld restart && sudo mkdir -p /run && sudo mkdir -p /usr/share/nginx/logs && sudo mv $REMOTE_HOME/nginx.conf /etc/nginx && sudo nginx -t && sudo setenforce permissive && sudo service nginx restart && sudo mv $REMOTE_HOME/selinux.conf /etc/selinux/config"

# TODO: https://fedoramagazine.org/protect-your-system-with-fail2ban-and-firewalld-blacklists/
