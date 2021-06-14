import glob
from datetime import datetime, timezone

import yaml
from feedgen.feed import FeedGenerator
from jinja2 import Environment, FileSystemLoader

blog_posts = []

def load_template(file, base):
    with open(file, "r") as f:
        return Environment(loader=FileSystemLoader(base+"/")).from_string(f.read())

base = "site"
out_base = "build"

events = yaml.load(open('data/events.yaml'))

for file in glob.glob(base+"/*.*")+glob.glob(base+"/**/*.*"):
    if file.endswith(".tmpl"):
        continue
    tmpl = load_template(file, base)
    out = file.replace(base+"/", out_base+"/")
    content = tmpl.render({ 'events': events })
    with open(out, "w") as fw:
        fw.write(content)

    # Accumulate blog posts
    if file.startswith(base+"/blog/") and not file.endswith("index.html"):
        ctx = tmpl.environment.context_class
        get_block = lambda name: next(tmpl.blocks[name](ctx))
        blog_posts.append({
            "title": get_block("postTitle"),
            "author": get_block("postAuthor"),
            "date": get_block("postDate"),
            "tags": get_block("postTags"),
            "url": file.replace(base+"/", ""),
            "content": content,
        })

tmpl = load_template(base+"/blog/index.html", base)
blog_posts.sort(key=lambda post: datetime.strptime(post["date"], "%B %d, %Y"), reverse=True)
with open(out_base+"/blog/index.html", "w") as fw:
    fw.write(tmpl.render(posts=blog_posts))

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
