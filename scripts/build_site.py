import os
import glob
import re
import shutil
import subprocess
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

{% block docbody %}
BACKLINK

BODY

<h4 class="about-this-page">About this page</h4>
<p>
  See an error or want to add a clarification? This page is
  generated from <a href="PAGE">this file on Github</a>.
  <br /><br />
  Last edited LAST_EDITED.
</p>
{% endblock %}"""

DOCS_SOURCE = "datastation-documentation"
DOCS_SITE_ROOT = "site/docs/"

def make_docs_glob(*suffixes):
    all = []
    for suffix in suffixes:
        all += glob.glob(f"{DOCS_SOURCE}/{suffix}") + glob.glob(f"{DOCS_SOURCE}/**/{suffix}", recursive=True)
    return all

# Copy any images/gifs over
for file in make_docs_glob("*.png", "*.gif"):
    shutil.copy(file, os.path.join(out_base, os.path.basename(file)))

# Rewrite md files from docs repo into HTML files for the site.
for file in make_docs_glob("*.md"):
    if '/internal/' in file:
        continue
    # Drops the first directory (the DOCS_SITE_ROOT)
    source = '/'.join(file.split('/')[1:])
    newfile = source.replace('.md', '.html').replace('README', 'index')
    if "LICENSE" in newfile:
        continue
    directory = DOCS_SITE_ROOT + os.path.dirname(newfile)
    if not os.path.exists(directory):
        os.makedirs(directory)

    with open(DOCS_SITE_ROOT + newfile, 'w') as f:
        with open(file) as original:
            original_file = original.read()
            raw = ''.join(original_file)
            raw = raw.replace('.md', '.html')
            raw = re.sub(r'([a-zA-Z0-9.\-_\/]*/([a-zA-Z0-9\-_]*\.(png|gif)))', r'https://cdn.jsdelivr.net/gh/multiprocessio/datastation-documentation@main\1', raw)

            html = marko.convert(raw)
            html = html.replace('<code>', '<code class="hljs">')
            html = re.sub(r'class="(language-[a-zA-Z0-9]+)"', r'class="hljs \1"', html)

            title = html[:html.index('</h1>')].split('<h1>')[1].strip()
            isroot = newfile == "index.html"
            if isroot:
                title = "Documentation"
            page = 'https://github.com/multiprocessio/datastation-documentation/blob/main/' + source

            file_to_check_time = source
            if source.startswith('latest'):
                without_latest = source[len('latest'):]
                file_to_check_time = os.readlink(DOCS_SOURCE + '/latest') + without_latest
            mtime = subprocess.check_output(['git', 'log', '-1', '--pretty=format:%ct', file_to_check_time], cwd=DOCS_SOURCE)

            last_edited = datetime.fromtimestamp(int(mtime.decode())).strftime("%b %d, %Y")

            backlink = '<div><a href="/docs/">Back to documentation</a></div>' if not isroot else ''

            replaced = DOCS_TEMPLATE.replace(
                'TITLE', title).replace(
                    'BACKLINK', backlink).replace(
                        'LAST_EDITED', last_edited).replace(
                            'PAGE', page).replace(
                                # Based on this dumb replace logic, BODY
                                # must be replaced last otherwise the
                                # previous replaces might match within the
                                # actual post body.
                                'BODY', html)

            f.write(replaced)

DEFAULT_DATA = {
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
