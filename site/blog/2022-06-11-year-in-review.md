{% extends "blog/layout.tmpl" %}

{% block postTitle %}One year as a solo dev building open-source data tools without funding{% endblock %}
{% block postDate %}June 10, 2022{% endblock %}
{% block postAuthor %}Phil Eaton{% endblock %}
{% block postAuthorEmail %}phil@multiprocess.io{% endblock %}
{% block postTags %}retro{% endblock %}

{% block postBody %}
I quit my job as an engineering manager at Oracle in early
June 2021. I had a bit of savings and a few contract opportunities so
I decided to see how far I could get building an app I've wanted for
years as a manager. I have never built my own app before and I've
never built a desktop app before. It seemed like a fun and helpful
idea! And in the best case I might be able to build a real company
around it.

As of a few days ago I've now been at this for 1 year. So it's time
for a retro!

Over the last 12 months I've garnered over 4,000 Github stars across 4
tools, 6 libraries, and 5 benchmark repos. I've written 19 blog posts
mostly about benchmarking (SQLite in Go, with and without cgo and
Speeding up Go's builtin JSON encoder up to 55% for large arrays of
objects) and explorations of databases (Surveying SQL parser libraries
in a few high-level languages and The world of PostgreSQL wire
compatibility). 5 of these posts have reached the front page of HN.

A few more stats:
* Over 1,100 unique users have ever opened the app
* Around 400 unique users open the app per month
* Around 50 users opening the app at least 3 times per month

In this post I'll share a bit about how I did this, the not very
successful process of finding funding or bootstrapping, and what is
going to happen next with DataStation. tldr; I'm heading back to
full-time employment.

First a little background on the problem. You can skip this part if
you just want to read about the process. :)

# Background

Data scientists and product managers have a wealth of tools available
to them to analyze data. Tools like Jupyter Notebooks and RStudio for
data scientists, Tableau and every BI tool (Looker, Power BI, Google
Data Studio, Metabase) and of course, Excel.

But backend developers and operations folk only have monitoring GUIs
like Grafana and DataDog, SQL IDEs like DBeaver and DataGrip, and code
IDEs or text editors.

Companies have a tendency to vastly simplify analytics because of lack
of tooling. One company I was at did analysis based only on data in
the SQL database. But not all your data is in SQL. As you scale, SQL
databases tend only to store the existence of info (a list of
customers for example). The activity of customers is stored in your
API logs. How often did they use the API (through the UI or
directly). How has that been trending over time. How is that linked to
their contract start/end date info stored in Salesforce. And so on.

There are almost no vendor-independent data analysis platforms for the
wealth of databases and data storage systems (i.e. APIs, files,
databases, etc.) that backend developers and operations folk deal
with. Your logs are in Elasticsearch or Splunk or CloudWatch. Your
customer data is in PostgreSQL or SQL Server or MongoDB. Your
analytics data is in Snowflake or ClickHouse or BigQuery. Your
internal APIs are behind REST interfaces. And then there are the
random CSVs and Excel sheets you get from business analysts and
product managers you need to integrate.

How do you query this data or join or filter across such disparate
sources? The only two solutions today are to put ALL data into a
warehouse or to write custom scripts. The problem with warehouses are
that they are expensive and that the ETL process for every new
database is expensive too. Tons and tons of companies are trying to
solve this. You'll get lost among all the vendors trying to capitalize
on the “Modern Data Stack”. They're expensive.

And in my experience enough companies don't even try to set up any
tooling in the first place other than read access to the MySQL
database (a specific example of a situation I was in in the
past). It's hard for managers to do analysis in these cases despite
all the relevant systems having working APIs.

If you're forced to write custom scripts you spend a lot of time
reading API docs. Some APIs are very complicated. I've written a
number of Elasticsearch API clients over the years with varying
degrees of success getting pagination and aggregation right on
Elasticsearch results.

So I built DataStation. It's a GUI app that just asks you for
database/API credentials and allows you to write the query. If you're
not happy with the query as is or you want to join data sources, you
can create additional workflow steps (called Panels) in your favorite
language (SQL, R, Julia, Python, JavaScript, Ruby, etc.) that map and
filter data.

Ultimately DataStation produces charts or tables you can export as
Markdown, HTML, SVG, CSV, etc.

# The first few weeks

I started with a purely in-browser prototype of DataStation with the
basics of panel interaction using a Python implementation in
JavaScript (Brython) and eval for JavaScript. You could load CSV and
JSON files. And you could make HTTP requests so long as CORS headers
were set. (Again this was all purely in-browser, no server or desktop
component).

It has been open-source since the first proof of concept commit on
Monday, June 7 2021.

The first few weeks were extremely painful. Everything felt so
slow. The biggest projects I'd personally published before then were
around 100-400 stars and it felt like ages until DataStation reached
even 10 stars. I did a Show HN of the in-browser demo on June 11, 2021
that got no upvotes. That same post did a little better on
Lobste.rs. And I posted an introductory blog post to HN on June 13,
2021 and that got 3 upvotes.

Getting 10 followers on Twitter felt similarly embarrassingly long.

A month later I still only had 60 Github stars. But I was content to
keep working toward a desktop version of DataStation and my general
goal was to blog and record demo videos for Youtube (which I did a few
times, like this one on June 14, 2021).

Somewhere during this time I broke my ankle longboarding (on the very
the first day). That was fun!

# Desktop

It took me around a month to go from the in-browser demo to a desktop
app using Electron. The July 2021 blog post announcing the first
desktop release got 3 upvotes on Lobsters and none on Hacker News.

I picked Electron because I wanted a cross-platform app built on
HTML/CSS/JavaScript. I wanted the bulk of DataStation functionality to
be available as a desktop app and as a typical web app. I also wanted
to be able to keep the in-browser mode around as a demo environment
for folks hesitant to download a random app. That in-browser app is
still around and supported today, though I kind of wish it wasn't
since it means more code to maintain and test.

Like I said I haven't built a desktop app before and this was a fairly
easy way to get started. The smallest I was able to get my release
zips was around 100MB. But that has grown as I've added more builtin
libraries to DataStation.

I built the releases manually on my Mac machine and Windows machine
and uploaded them directly to the Github release UI. When I added
Linux binaries I built those within a VM on my Mac and uploaded them
directly too.

I was releasing about once a week at that time. So by the end of July
after a few manual build/uploads and lots of bugs I added a scripted
release process in Github Actions that both built and uploaded the zip
files. And I added end-to-end tests for the Electron app on all
supported platforms.

# Enter VCs

By September DataStation had about 200 stars on Github and somehow
folks at VCs started noticing it. The first came in the end of
September. It was one of the bigger VCs which was both cool and
scary. I threw together a terrible deck (I had no idea what I was
doing). We chatted for 15/20 minutes and he said it was too early but
he'd like to stay in touch.

That same sort of interaction happened repeatedly for a couple more
VCs. I don't know for sure where they found DataStation but
undoubtedly because I posted screenshots and demos on Twitter or
shared blog posts on Hacker News.

When I spoke with VCs it felt like I was speaking with aliens. It's
not that they made no sense it's that what they I couldn't understand
what they wanted and they didn't understand the problem I was trying
to solve and where I was headed. I don't blame them of course it's a
combination of my job to explain well and also to find the right fit
of VCs who understand the problem. Or maybe the idea is not something
that should be VC funded.

After months of learning (but ultimately getting nowhere) talking to
these inbound VCs, and receiving no responses from outbound VCs, I got
depressed and decided to stop talking to VCs for a while and just
focus on DataStation usability, stability and documentation.

DataStation today is still solely funded on my savings.

# dsq

One thing DataStation allows you to do is run SQL on any kind of
data. In December 2021 I realized this would be extremely useful as a
CLI app. The panel evaluation code was written in Go so I exposed it
as a library and wrote a ~200 line wrapper around it.

It is a CLI that allows the user to specify data files and a SQL
query.

$ dsq testdata/userdata.parquet 'select count(*) from {}' | jq
[
  {
    "count(*)": 1000
  }
]

Just like DataStation you can join multiple different data sources
(with different original data formats).

$ dsq testdata/join/users.csv testdata/join/ages.json \
  "select u.name, a.age from {0} u join {1} a on u.id = a.id"
[{"age":88,"name":"Ted"},
{"age":56,"name":"Marjory"},
{"age":33,"name":"Micah"}]

I wrote a blog post describing dsq which hit the front of HN. The dsq
repo blew up, bringing DataStation along with it. Within a month dsq
hit 1,000 Github stars and DataStation went from ~600 to ~1,000 stars
during that time.

# Documentation

Until around November (about 5 months) there was no documentation for
DataStation at all. There were demo videos and a few release blog
posts with screenshots. I often heard from users that they opened the
app and didn't understand what to do and didn't go back. That made
sense! There was no onboarding in the app either.

But I didn't want to work on documentation because I was still focused
on building the basic features I felt were needed and improving
stability and performance. There were some infrequent but particularly
bad bugs in the project storage layer that I wanted to work through
before I built out high-level tutorials that I knew would invite more
users.

In November 2021 I created the datastation-documentation repo and
started adding docs for panels.

And by January 2022 I was comfortable with the state of stability so I
started writing tutorials for connecting to databases. And I was
determined to do them well.

Every tutorial that can use Docker shows you the steps for how to set
up Docker and add test data to it. It shows with GIFs how to connect
to the database in DataStation and how to use DataStation to query and
work with data from the database.

I am pretty sure the DataStation tutorials are one of the best places
on the internet for understanding how to set up a working Docker
container for every major database and get test data into it. I will
be referring back to those docs for years. And they're only going to
cover more databases.

# Community

I wanted to build not just a product (or products) but also a
community. I started on this (a
[Discord](https://discord.multiprocess.io)) a little late though, November 2021 I think. And
rather than focusing specifically on data as a community I decided to
focus on software internals in general. I probably wouldn't pick a
tangent community like this in the future but it's a topic I'm
interested in in the long-run and it has attracted a fun group of
people. Over 800 to date actually.

In January 2022 I [started a virtual
Meetup](https://www.meetup.com/hackernights/) on the same
topic, software internals, that has happened to feature a number of
data hackers. It reached 300 members recently. With 10-30 showing up
for each time.

One funny bit about virtual meetups is that randos join and cause
havoc like blasting music or impersonating another user by name and
badmouthing people in chat. I tried a few different things but
ultimately it looks like I'm going to go the speakeasy route of a
word-of-mouth password.

Basically, don't put a Zoom link with a password in the link on
Meetup.com. Find some other way to give people the password. This is
annoying for public meetups that are just getting started but I guess
it is what it is.

# Contributors

DataStation is a pretty complex app compared to ones I built in the
past. While I wanted contributors because of what it implies (that
your app is useful and people *want* to improve it) I wasn't sure how
on earth I'd support them.

dsq turned out to be the easiest way to onboard contributors. It's a
CLI that doesn't require cross-platform desktop testing (which is much
harder than just cross-platform CLI testing). It doesn't require
changing code in multiple places (the UI and the backend, at
least). And it is written in Go.

I started getting contributors this year, developers who noticed
issues in dsq and submitted patches to DataStation (since its where
the core of dsq functionality is).

I had been marking issues as "Good first issue" in Github issues since
the beginning of the project but I never got any takers. So I decided
to try a new route earlier this year, creating a
[GOOD_FIRST_PROJECTS.md](https://github.com/multiprocessio/datastation/blob/main/GOOD_FIRST_PROJECTS.md)
and sharing it on relevant threads on HN and Reddit about how to get
started contributing to OSS.

This has been surprisingly effective. Since writing that guide and
sharing on relevant HN/Reddit threads I've had a few serious
contributors. One of them submitting 6 pull requests between
DataStation and dsq. Another submitting two pull requests to dsq.

Just folks who want to get some practice with OSS and coding in a real
project.

These numbers aren't massive but they're not nothing!

# What's next

Without funding I'm ready to head back to employment. I am excited to
keep working on DataStation/dsq, both of which are completely
open-source, and I hope to introduce DataStation as an analytics and
reporting tool wherever I land.

I'm particularly interested in ending up at a database or analytics
company. So if you're a database or analytics company hiring managers
or developers, feel free to [message me](phil@multiprocess.io)!

Otherwise, join the community on
[Discord](https://discord.multiprocess.io/) or
[Meetup.com](https://meetup.com/hackernights) and stick around for
more updates on DataStation/dsq open source!

{% endblock %}
