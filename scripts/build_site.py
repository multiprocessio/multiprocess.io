import os
import glob
from datetime import datetime, timezone

import yaml
from feedgen.feed import FeedGenerator
from jinja2 import Environment, FileSystemLoader
import marko

base = "site"
out_base = "build"

DOCS_TEMPLATE = """{# DO NOT EDIT -- THIS FILE IS AUTO-GENERATED #}

{% set doctitle = 'TITLE' %}

{% extends 'docs/layout.tmpl' %}
/
{% block docbody %}
BODY
{% endblock %}"""
for file in glob.glob("datastation-documentation/*.md") + glob.glob("datastation-documentation/**/*.md", recursive=True):
    newfile = '/'.join(file.split('/')[1:]).replace('.md', '.html').replace('README', 'index')
    if "LICENSE" in newfile:
        continue
    docs_root = "site/docs/"
    directory = docs_root + os.path.dirname(newfile)
    if not os.path.exists(directory):
        os.makedirs(directory)

    with open(docs_root + newfile, 'w') as f:
        with open(file) as original:
            original_file = original.read()
            raw = ''.join(original_file)
            raw = raw.replace('.md', '.html')

            html = marko.convert(raw)
            html = html.replace('<code>', '<code class="hljs">')

            title = html[:html.index('</h1>')].split('<h1>')[1].strip()
            # Drop first header
            html = html[html.index('</h1>') + len('</h1>'):]
            if newfile == "index.html":
                title = "Documentation"

            f.write(DOCS_TEMPLATE.replace('TITLE', title).replace("BODY", html))

DEFAULT_DATA = {
    "latest_version": '0.2.0',
    "title": "DataStation | The Data IDE for Developers",
    "description": "DataStation is an open-source data IDE for developers. It allows you to easily build graphs and tables with data pulled from SQL databases, logging databases, metrics databases, HTTP servers, and all kinds of text and binary files. Need to join or munge data? Write embedded scripts as needed in Python, JavaScript, Ruby, R, or Julia. All in one application."
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

videos = yaml.load(open('data/videos.yaml'), yaml.Loader)
events = yaml.load(open('data/events.yaml'), yaml.Loader)

for file in glob.glob(base+"/*.*")+glob.glob(base+"/**/*.*", recursive=True):
    if not file.endswith('.html'):
        continue
    print('Rendering ' + file)
    tmpl = load_template(file, base)
    out = file.replace(base+"/", out_base+"/")
    title = get_block(tmpl, "title")
    content = tmpl.render({ **DEFAULT_DATA, "events": events, "videos": videos })

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

    directory = os.path.dirname(out)
    if not os.path.exists(directory):
        os.makedirs(directory)

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
