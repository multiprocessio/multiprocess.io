{% extends "blog/layout.tmpl" %}

{% block postTitle %}Container scheduling strategies for integration testing 14 different databases in Github Actions{% endblock %}
{% block postDate %}July 25, 2022{% endblock %}
{% block postAuthor %}Phil Eaton{% endblock %}
{% block postAuthorEmail %}phil@multiprocess.io{% endblock %}
{% block postTags %}testing,databases,containers,github actions{% endblock %}

{% block postBody %}
DataStation lets you query over 20 SQL and non-SQL data systems. 14+
databases can be tested locally (in Docker; even SQL Server and Oracle!).

Integration testing DataStation support for these databases is the
most important part of developing DataStation. Thankfully, since
DataStation is an open-source project, these integration tests can run
freely in Github Actions.

I'm going to focus on the data systems that can be tested
locally in Docker.

![A list of DataStation database test files](/integration-tests.png)

# Every database, everywhere at once

When I first started integration testing databases in DataStation I
did one of two things:

1. Ran docker images in the background
2. Installed databases globally from Ubuntu packages

One of these two steps happened for each database that needed to be
tested. The process ran as part of a setup script.

For example, here are the parts of the [setup script for Github
Actions](https://github.com/multiprocessio/datastation/blob/3362433dc5cce51760cbac8f800e3befce59a072/scripts/ci/prepare_linux_integration_test_setup_only.sh)
that set up MySQL and PostgreSQL. (This is an old commit, it's no
longer done like this. As you'll see further on.)

```bash
# Set up MySQL
sudo service mysql start
sudo mysql -u root -proot --execute="CREATE USER 'test'@'localhost' IDENTIFIED BY 'test'";
sudo mysql -u root -proot --execute="CREATE DATABASE test";
sudo mysql -u root -proot --execute="GRANT ALL PRIVILEGES ON test.* TO 'test'@'localhost'";

# Set up PostgreSQL
sudo apt-get install postgresql postgresql-contrib
echo "
local  test            test                md5
host   test            test   localhost    md5
local  all             all                 peer" | sudo tee /etc/postgresql/12/main/pg_hba.conf
sudo service postgresql restart
sudo -u postgres psql -c "CREATE USER test WITH PASSWORD 'test'"
sudo -u postgres psql -c "CREATE DATABASE test"
sudo -u postgres psql -c "GRANT ALL ON DATABASE test TO test"
```

And here is later on in the same script where Docker containers for
QuestDB, Elasticsearch, and Prometheus are set up to run in the
background.

```bash
# Start up questdb
docker run -d -p 8812:8812 questdb/questdb

# Start up elasticsearch
docker run -d -p 9200:9200 -e "discovery.type=single-node" docker.elastic.co/elasticsearch/elasticsearch:7.16.3

# Start up prometheus
docker run -d -p 9090:9090 -v $(pwd)/testdata/prometheus:/etc/prometheus prom/prometheus
```

This was the easy, lazy way to get tests working. But there were two
big problems. First off, it was horrible to test these databases
locally. When working on tests, you'd have to leave the test file and
go into this CI setup script and find the lines that set a database
up. If you were trying to test outside of Ubuntu and needed to run one
of these databases set up using Ubuntu packages you'd have to figure
out how to translate those steps to your OS/distro.

The second big problem was that after months of adding new databases
and new database containers for new database tests, Github Actions was
crawling to a halt. After setting up the 14th running database
(MongoDB) last week, this workflow on Github Actions crashed
repeatedly for a week.

# Per-test scheduling

So I decided to solve both problems at once by writing a small helper
function, `withDocker`, that each test could call and declare the
container setup it needed for its tests to work. The goal here was
that 1) all of these local database tests would now only require
Docker and 2) each database would only run so long as it was
needed. No more 14 databases running at the same time in Github
Actions.

Here's an example ([source code
here](https://github.com/multiprocessio/datastation/blob/main/integration/scylla.test.js))
of the `useDocker` helper for running a
[ScyllaDB](https://www.scylladb.com/) container, setting the stage for
DataStation tests to run for Scylla integration.

```javascript
... imports ...

describe('basic cassandra/scylladb tests', () => {
  test(`runs basic cql query`, async () => {
    await withDocker(
      {
        image: 'docker.io/scylladb/scylla:latest',
        port: '9042',
        program: [
          '--smp',
          '1',
          '--authenticator',
          'PasswordAuthenticator',
          '--broadcast-address',
          '127.0.0.1',
          '--listen-address',
          '0.0.0.0',
          '--broadcast-rpc-address',
          '127.0.0.1',
        ],
        cmds: [
          `cqlsh -u cassandra -p cassandra -e "CREATE KEYSPACE test WITH REPLICATION = {'class': 'SimpleStrategy', 'replication_factor': 1};"`,
          `cqlsh -u cassandra -p cassandra -e "CREATE ROLE test WITH PASSWORD = 'test' AND LOGIN = true AND SUPERUSER = true;"`,
        ],
      },
      async () => {
	    ... do actual test stuff ...
      }
    );
  }, 360_000);
});
```

One really useful part of `withDocker` is that when you specify `cmds`
it will re-run the first element in the list until it succeeds. This
is an easy shorthand for waiting for the container to become available
so long as you know the command *should* succeed in normal conditions.

Also, all commands in the `cmds` list get run within the Docker
container with by prefixing the command with `docker exec
$containerId`.

## More manual waiting

When you need to wait on something outside of the container you can fill
out the optional `wait` callback. Here's an example ([source code
here](https://github.com/multiprocessio/datastation/blob/main/integration/elasticsearch.test.js))
of using the `wait` callback to make sure that data has been ingested
into Elasticsearch before allowing tests to run.

```javascript
... imports ...

describe('elasticsearch testdata/documents tests', () => {
  const tests = [
    ... some test data ...
  ];

  for (const testcase of tests) {
    test(
      'query: "' + testcase.query + '"',
      async () => {
        await withDocker(
          {
            port: 9200,
            env: {
              'discovery.type': 'single-node',
            },
            image: 'docker.elastic.co/elasticsearch/elasticsearch:7.16.3',
            wait: async () => {
              console.log('Awaiting container');
              while (true) {
                try {
                  const r = await fetch('http://localhost:9200');
                  break;
                } catch (e) {
                  await new Promise((r) => setTimeout(r, 2000));
                }
              }

              // Setting up test docs
              const nDocs = 4;
              for (let i = 0; i < nDocs; i++) {
                cp.execSync(
                  `curl --fail -X POST -H 'Content-Type: application/json' -d @testdata/documents/${
                    i + 1
                  }.json http://localhost:9200/test/_doc`,
                  { stdio: 'inherit' }
                );
              }

              // Wait until all docs have been ingested
              while (true) {
                console.log('Waiting for all docs to be ready');
                try {
                  const r = await fetch('http://localhost:9200/test/_search');
                  const j = await r.json();
                  console.log(j);
                  if (j.hits.hits.length === nDocs) {
                    break;
                  }
                } catch (e) {
                  /* pass */
                }

                await new Promise((r) => setTimeout(r, 2000));
              }
            },
          },
          async () => {
            ... do the actual test ...
          }
        );
      },
      360_000
    );
  }
});
```

Using `cmds` or `wait` lets me almost fully avoid using `sleep()` as
the sole way for deciding when tests can be run. But out of laziness,
there are some exceptions. For example I haven't yet figured out a CLI
or `curl` based way to test for when Oracle is ready so I just `await
new Promise(r => setTimeout(r, 60_000))`; i.e. [wait one
minute](https://github.com/multiprocessio/datastation/blob/main/integration/oracle.test.js#L34).

## `withDocker` implementation

You can find the [full code on a Github Gist
here](https://gist.github.com/eatonphil/78df2e2309f6804491840aeb5e40acd9). It's
not perfect and I don't want to maintain it for others. But it might
be a useful base for others that are interested in similar style
testing.

# Impact and next steps

Before this, in the last few weeks after we added the 14th running
databases, tests were hanging in Github Actions after 45-ish
minutes. Now tests are finishing reliably in under 30 minutes (10
minutes goes to setup).

One shortcut I took in the `withDocker` implementation is putting a
hack-y lock in JavaScript on a single image running at a time. And I
made this behavior stronger by requiring jest to run one test at a
time with `--runInBand`; not scheduling tests onto worker
processes. This was to block tests from failing because a port was in
use.

This may be slowing down tests but it may also be possible that
multiple containers running at once would cause less work to be done
in the shared compute environment that is free Github Actions. I'm not
sure.

The way I'm thinking about trying without locks is by having the
`withDocker` function pick a free port and sending it to the
callback. Then it could schedule all tests at once without port
conflicts. And then without jest's `--runInBand` flag in place jest
could share work across a few processes. I'll have to try it out to
see if it improves overall test runtime.

#### Share

<blockquote class="twitter-tweet"><p lang="en" dir="ltr">Here&#39;s a new blog post on how integration testing 14+ databases has evolved in DataStation.<br><br>From running 14 databases in Github Actions all at once<br><br>To building a `withDocker()` helper in Node.js so each jest test can schedule its own container<a href="https://t.co/p1WqJQeq8F">https://t.co/p1WqJQeq8F</a> <a href="https://t.co/7YBq2VBjWW">pic.twitter.com/7YBq2VBjWW</a></p>&mdash; Multiprocess Labs (@multiprocessio) <a href="https://twitter.com/multiprocessio/status/1552362075208515587?ref_src=twsrc%5Etfw">July 27, 2022</a></blockquote> <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>
{% endblock %}
