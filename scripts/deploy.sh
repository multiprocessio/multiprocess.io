#!/usr/bin/env bash

set -eu

version=""
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -v|--datastation-version)
	    version="$2"
	    shift
	    ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

if [[ -z $version ]]; then
    echo "--datastation-version not set"
    exit 1
fi

set -x

git clean -xid
./scripts/build_site.sh

git clone git@github.com:multiprocessio/datastation workspace || true
( cd workspace && git pull && yarn && UI_ESBUILD_ARGS="--minify" yarn build-ui )

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
remote_copy "home/*" $REMOTE_HOME/home
remote_copy scripts/setup_tls.sh $REMOTE_HOME/setup_tls.sh
remote_copy config/nginx.conf $REMOTE_HOME/nginx.conf
remote_copy config/crontab $REMOTE_HOME/crontab
remote_copy config/selinux.conf $REMOTE_HOME/selinux.conf

remote_run "sed -i 's/__VERSION_REPLACE__/$version/g' $REMOTE_HOME/nginx.conf"

SLEEPTIME="$(awk 'BEGIN{srand(); print int(rand()*(3600+1))}')"
remote_run "sudo dnf update -y && sudo dnf install -y nginx cronie cronie-anacron && sudo systemctl enable nginx && sudo firewall-cmd --add-service=http && sudo firewall-cmd --add-service=https && sudo service firewalld restart && sudo mkdir -p /run && sudo mkdir -p /usr/share/nginx/logs && sudo mv $REMOTE_HOME/nginx.conf /etc/nginx && sudo nginx -t && (sudo setenforce permissive || echo selinux disabled) && sudo service nginx restart && sudo mv $REMOTE_HOME/selinux.conf /etc/selinux/config && sudo mv $REMOTE_HOME/crontab /etc/crontab"

# TODO: https://fedoramagazine.org/protect-your-system-with-fail2ban-and-firewalld-blacklists/
