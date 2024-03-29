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
never built a desktop app before.

Over the last 12 months I've garnered over 4,000 Github stars across 4
tools, 6 libraries, and 5 benchmark repos. I've written 19 blog posts
mostly about benchmarking ([SQLite in Go, with and without cgo](https://datastation.multiprocess.io/blog/2022-05-12-sqlite-in-go-with-and-without-cgo.html) and
[Speeding up Go's builtin JSON encoder up to 55% for large arrays of
objects](https://datastation.multiprocess.io/blog/2022-03-03-improving-go-json-encoding-performance-for-large-arrays-of-objects.html) and explorations of databases ([Surveying SQL parser libraries
in a few high-level languages](https://datastation.multiprocess.io/blog/2022-04-11-sql-parsers.html) and [The world of PostgreSQL wire
compatibility](https://datastation.multiprocess.io/blog/2022-02-08-the-world-of-postgresql-wire-compatibility.html)). 5 of these posts have reached the front page of HN.

A few more stats about DataStation specifically:
* Over 1,100 unique users have ever opened the app
* Around 400 unique users open the app per month
* Around 50 users opening the app at least 3 times per month

I also ended up talking to dozens of investors and interviewing
(unsuccessfully) with YCombinator.

In this post I'll share a bit about how I did this, the not very
successful process of finding funding, and what happens
next. Basically, everything stays open-source, I'm still extremely
excited about using and working on DataStation, and I'm actively
interviewing. :)

First a little background on the problem. You can skip this part if
you just want to read about the process.

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
API logs. How often did they use the API (through the UI or directly)?
How has that been trending over time? How is that linked to their
contract start/end date info stored in Salesforce? These questions can
only be answered by extreme denormalization or joining across
databases.

Your logs are in Elasticsearch or Splunk or CloudWatch. Your
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
JavaScript ([Brython](https://www.brython.info/)) and eval for JavaScript. You could load CSV and
JSON files. And you could make HTTP requests so long as CORS headers
were set. (Again this was all purely in-browser, no server or desktop
component).

It has been [open-source](https://github.com/multiprocessio/datastation) since the first proof of concept commit on
Monday, June 7 2021.

<img class="no-shadow" src="https://pbs.twimg.com/media/E3yxGEBWQAEQSSK?format=png&name=4096x4096" alt="An early screenshot" />

The first few weeks were extremely painful. Everything felt so
slow. The biggest projects I'd personally published before then were
around 100-400 stars and it felt like ages until DataStation reached
even 10 stars. I did a [Show HN](https://news.ycombinator.com/item?id=27478060) of the in-browser demo on June 11, 2021
that got no upvotes. That same post did [a little better on
Lobste.rs](https://lobste.rs/s/mecdh3/browser_open_source_data_ide_for). And I posted [an introductory blog post to HN](https://news.ycombinator.com/item?id=27495223) on June 13,
2021 and that got 3 upvotes.

Getting to 10 followers [on Twitter](https://twitter.com/multiprocessio) felt similarly embarrassingly long.

A month later I still only had 60 Github stars. But I was content to
keep working toward a desktop version of DataStation and my general
goal was to blog and record demo videos for Youtube (which I did a few
times, like [this one](https://www.youtube.com/watch?v=_7LEV3ZeQWU&list=PL2t91m2RvccpsXbMtz4sNZ_AExXX-nxPr&index=7) on June 14, 2021).

# Desktop

It took me around a month to go from the in-browser demo to a desktop
app using Electron. The July 2021 blog post announcing the first
desktop release got 3 upvotes on Lobsters and none on Hacker News.

<img class="no-shadow" src="https://pbs.twimg.com/media/E5KLXcrXEAAEK_L?format=jpg&name=4096x4096" alt="First desktop release" />

I picked Electron because I wanted a cross-platform app built on
HTML/CSS/JavaScript. I wanted the bulk of DataStation functionality to
be available as a desktop app and as a typical web app. I also wanted
to be able to keep the in-browser mode around as a demo environment
for folks hesitant to download a random app. That [in-browser app is
still around and supported today](https://app.datastation.multiprocess.io/), though I kind of wish it wasn't
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
after a few manual build/uploads and lots of bugs I added a [scripted
release process in Github Actions that both built and uploaded the zip
files](https://github.com/multiprocessio/datastation/blob/main/.github/workflows/releases.yml). And I added end-to-end tests for the Electron app on all
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
not that they made no sense it's that I couldn't understand
what they wanted or how they wanted things presented. And they didn't understand the problem I was trying
to solve or where I was headed. Most of them didn't know Kibana, one of the most similar SaaS products.

I don't blame them of course. It was a combination of 1) me not
explaining well and 2) not focusing on talking to the right VCs who
understand the space. Or maybe the idea is not something that should
be VC funded.

After months of learning (but ultimately getting nowhere) talking to
these inbound VCs, and receiving no responses from outbound VCs, I got
frustrated and decided to stop talking to VCs for a while and just
focus on DataStation usability, stability and documentation.

# dsq

One thing DataStation allows you to do is run SQL on any kind of
data. In December 2021 I realized this would be extremely useful as a
CLI app. The panel evaluation code in DataStation was written in Go so I exposed it
as a library and wrote a ~200 line wrapper around it.

That wrapper is a CLI that allows the user to specify data files and a SQL
query.

```
$ dsq testdata/userdata.parquet 'select count(*) from {}' | jq
[
  {
    "count(*)": 1000
  }
]
```

Just like DataStation you can join multiple different data sources
(with different original data formats).

```
$ dsq testdata/join/users.csv testdata/join/ages.json \
  "select u.name, a.age from {0} u join {1} a on u.id = a.id"
[{"age":88,"name":"Ted"},
{"age":56,"name":"Marjory"},
{"age":33,"name":"Micah"}]
```

I [wrote a blog post](https://datastation.multiprocess.io/blog/2022-01-11-dsq.html) describing dsq which [hit the front of HN](https://news.ycombinator.com/item?id=29892463). The dsq
repo blew up, bringing DataStation along with it. Within a month dsq
hit 1,000 Github stars and DataStation went from ~600 to ~1,000 stars
during that time.

![DataStation and dsq star history](/star-history-2022614.png)

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

In November 2021 I created the
[datastation-documentation](https://github.com/multiprocessio/datastation-documentation)
repo and started adding docs for panels.

And by January 2022 I was comfortable with the state of stability so I
started writing tutorials for connecting to databases. And I was
determined to do them well.

Every tutorial that can use Docker shows you the steps for how to set
up Docker and add test data to it. It shows with GIFs how to connect
to the database in DataStation and how to use DataStation to query and
work with data from the database. For example, check out the [Google
Sheets + SQL: Querying Google Sheets with DataStation
](https://datastation.multiprocess.io/docs/tutorials/Query_Google_Sheets_with_DataStation.html)
tutorial.

I am pretty sure the [DataStation tutorials](https://datastation.multiprocess.io/docs/#tutorials) are one of the best places
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
project; volunteers.

# YC and the front of HN

In May I interviewed with YCombinator. I stressed out a lot about the
interview but it ended up being extremely friendly and positive. I
pitched building a SaaS offering where teams can work on projects
together and have hosted dashboards and recurring exports.

Later that day they told me no with a great email. They weren't a fan
of me being a solo founder and they felt the usage wasn't high enough.

Lots of successful founders have failed YC interviews so it doesn't
really bother me. It was a neat experience and maybe I'll do better
next time!

Unrelatedly, I decided to submit DataStation on HN as a Show HN and
[it reached the front
page](https://news.ycombinator.com/item?id=31574317). :)

# Fun parts, hard parts and a supportive spouse

The most fun parts were solving a problem I've had for years, digging
into database internals, optimizing Go code, working on a desktop app,
and building a community of like-minded hackers. It's been awesome to
see people use and share DataStation and dsq, report bugs, and
contribute code or suggestions.

The hard parts were the initial slowness of building a community and
project and user group from nothing. Every single time I reached a
milestone it immediately felt like the new normal and wasn't good
enough.

I missed working on a team, the entire time. The Discord and Meetup
groups helped eventually. And there's also a great reward of
successfully working with paying customers. Not (yet) having a product
I sold, I got no such reward.

Credit where due, I would not have been able to go this long without
my extremely supportive wife. While we agreed for me to take some time
off I thought she'd be asking me to go back to work after a few
months. Instead she continued to push me to keep working on
DataStation even when I got frustrated or depressed.

# What's next

Without funding I'm ready to head back to full-time employment. I am
excited to keep working on DataStation/dsq, both of which are
completely open-source, and I hope to introduce DataStation as an
analytics and reporting tool wherever I land.

I'm particularly interested in ending up at a database or analytics
company. So if you're a database or analytics company hiring managers
or developers, feel free to [message me](mailto:phil@multiprocess.io)!

Otherwise, join the community on
[Discord](https://discord.multiprocess.io/) or
[Meetup.com](https://meetup.com/hackernights) and stick around for
more updates on DataStation/dsq open source!

<img class="no-shadow" src="https://github.com/multiprocessio/datastation/blob/main/screens/the-basics-database-panel.png?raw=true" alt="DataStation today" />

## Share

<blockquote class="twitter-tweet"><p lang="en" dir="ltr">I&#39;ve been hacking on DataStation for a year now so time for a retro and what&#39;s next!<br><br>4k+ stars in 15 repos. 7 posts on the front of HN. Dozens of failed investor chats (including YC).<br><br>tldr; DataStation has a bright future &amp; I&#39;m on the job market. :)<a href="https://t.co/iFXoMsWC8Y">https://t.co/iFXoMsWC8Y</a> <a href="https://t.co/mBMlm6uLkz">pic.twitter.com/mBMlm6uLkz</a></p>&mdash; Phil Eaton (@phil_eaton) <a href="https://twitter.com/phil_eaton/status/1536677877596315648?ref_src=twsrc%5Etfw">June 14, 2022</a></blockquote> <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>

{% endblock %}
