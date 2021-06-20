./analytics/top_pages.sh | xargs -I {} bash -c 'cat /usr/share/nginx/logs/datastation.access.log | grep {} | jq -r ".http_referer"' | sort | uniq -c | sort -nr
