import glob
from datetime import datetime, timezone

import yaml
from feedgen.feed import FeedGenerator
from jinja2 import Environment, FileSystemLoader

DEFAULT_DATA = {
    "latest_version": '0.0.2-alpha',
    "title": "DataStation | The Data IDE for Developers",
}

blog_posts = []

def load_template(file, base):
    with open(file, "r") as f:
        return Environment(loader=FileSystemLoader(base+"/")).from_string(f.read())

def get_block(tmpl, name):
    ctx = tmpl.environment.context_class
    if name in tmpl.blocks:
        return next(tmpl.blocks[name](ctx))

    return None

base = "site"
out_base = "build"

events = yaml.load(open('data/events.yaml'))

for file in glob.glob(base+"/*.*")+glob.glob(base+"/**/*.*"):
    if file.endswith(".tmpl"):
        continue
    print('Rendering ' + file)
    tmpl = load_template(file, base)
    out = file.replace(base+"/", out_base+"/")
    title = get_block(tmpl, "title")
    content = tmpl.render({ **DEFAULT_DATA, "events": events })

    # Accumulate blog posts
    if file.startswith(base+"/blog/") and not file.endswith("index.html"):
        title = get_block(tmpl, "postTitle")
        tags = [t.strip() for t in get_block(tmpl, "postTags").split(',')]
        content = tmpl.render({ **DEFAULT_DATA, "events": events, "title": title, "tags": tags })
        blog_posts.append({
            "title": title,
            "author": get_block(tmpl, "postAuthor"),
            "date": get_block(tmpl, "postDate"),
            "tags": tags,
            "url": file.replace(base+"/", ""),
            "content": content,
        })

    with open(out, "w") as fw:
        fw.write(content)

tmpl = load_template(base+"/blog/index.html", base)
blog_posts.sort(key=lambda post: datetime.strptime(post["date"], "%B %d, %Y"), reverse=True)
with open(out_base+"/blog/index.html", "w") as fw:
    print('Rendering blog index')
    fw.write(tmpl.render(**DEFAULT_DATA, posts=blog_posts))

url_base = "https://datastation.multiprocess.io"

fg = FeedGenerator()
for post in blog_posts:
    fe = fg.add_entry()
    fe.id(url_base+"/"+post["url"])
    fe.title(post["title"])
    fe.author(name=post["author"])
    fe.link(href=url_base + "/" + post["url"])
    fe.pubDate(datetime.strptime(post["date"], "%B %d, %Y").replace(tzinfo=timezone.utc))
    fe.content(post["content"])

fg.id(url_base)
fg.link(href=url_base)
fg.title("DataStation Blog")
fg.description("DataStation | The Data IDE for Developers")
fg.language("en")
fg.rss_file(out_base+"/blog/rss.xml")

with open(out_base+"/sitemap.xml", "w") as f:
    urls = []
    for post in blog_posts:
        urls.append("""  <url>
    <loc>{url_base}/{url}</loc>
    <lastmod>{date}</lastmod>
 </url>""".format(url_base=url_base, url=post["url"], date=datetime.strptime(post["date"], '%B %d, %Y').strftime('%Y-%m-%d')))

    f.write("""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}
</urlset>""".format(urls='\n'.join(urls)))

with open(out_base+"/robots.txt", "w") as f:
    f.write("""User-agent: *
Allow: /

Sitemap: {url_base}/sitemap.xml""".format(url_base=url_base))
