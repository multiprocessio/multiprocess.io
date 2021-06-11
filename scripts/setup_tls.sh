sudo wget https://dl.eff.org/certbot-auto -O /usr/sbin/certbot-auto
sudo chmod a+x /usr/sbin/certbot-auto
sudo certbot-auto --os-packages-only
sudo certbot-auto --nginx
