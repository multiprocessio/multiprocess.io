# Add domain here for each new domain and run on the box

sudo certbot certonly \
     -d datastation.multiprocess.io \
     -d multiprocess.io \
     -d discord.multiprocess.io \
     -d app.datastation.multiprocess.io
