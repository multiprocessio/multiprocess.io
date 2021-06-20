cat /usr/share/nginx/logs/$1.access.log |jq --unbuffered -r 'select(.status = 200 )|.request' | grep GET | grep -v '.xml\|.css\|.txt\|.ico\|.png\|.php' | sort | uniq | cut -d ' ' -f 2
