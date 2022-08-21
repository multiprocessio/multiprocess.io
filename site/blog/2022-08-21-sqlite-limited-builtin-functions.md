{% extends "blog/layout.tmpl" %}

{% block postTitle %}SQLite has pretty limited builtin functions{% endblock %}
{% block postDate %}August 21, 2022{% endblock %}
{% block postAuthor %}Phil Eaton{% endblock %}
{% block postAuthorEmail %}phil@multiprocess.io{% endblock %}
{% block postTags %}sqlite,duckdb,postgresql,go{% endblock %}

{% block postBody %}
SQLite is the core of
[DataStation](https://github.com/multiprocessio/datastation) and
[dsq](https://github.com/multiprocessio/dsq).

So a while ago I tried to use DataStation/dsq to analyze some
benchmarks I had done that generated CSVs. But I quickly realized
how limited SQLite's standard library is.

SQLite only comes with
[these](https://www.sqlite.org/lang_aggfunc.html)
[few](https://www.sqlite.org/lang_datefunc.html)
[core](https://www.sqlite.org/windowfunctions.html)
[functions](https://www.sqlite.org/lang_corefunc.html). A few
[JSON](https://www.sqlite.org/json1.html) functions have recently
become builtin too.

### Aggregate functions

I wanted to get average and standard deviation values from my
benchmark result CSVs.

But there are only 7 builtin aggregate functions: `avg`, `count`,
`group_concat`, `min`, `total`, `max`, and `sum`.

There's no builtin standard deviation function. I'd need to write an
extension.

In contrast, [DuckDB](https://github.com/duckdb/duckdb) (an analytics
database otherwise very similar to SQLite) comes with a [suite of
statistics aggregation
functions](https://duckdb.org/docs/sql/aggregates). Even PostgreSQL
has a [wealth of statistical aggregation
functions](https://www.sqlite.org/lang_mathfunc.html).

If I had to choose between SQLite and DuckDB for ad-hoc analysis of
datasets on the command line I'd probably pick DuckDB for its
more convenient standard library.

However, DataStation/dsq use SQLite. So to bridge the gap I
published a standard library for
SQLite, called [go-sqlite3-stdlib](https://github.com/multiprocessio/go-sqlite3-stdlib). The
standard library is written in Go and mostly wraps existing
statistical (and other) libraries, providing a useful set of functions
to Go users embedding SQLite.

It adds statistical aggregation functions like discrete and
continuous percentiles, standard deviation, and so on.

![Aggregation functions](/0.11.0-stdlib-aggregation.png)

Since DataStation/dsq now registers `go-sqlite3-stdlib`, you
can do much more statistical analysis in DataStation/dsq.

Furthermore, not just DataStation/dsq but anyone who uses SQLite in Go
can register this standard library. The registration functions are
specific to [mattn/go-sqlite3](https://github.com/mattn/go-sqlite3)
today but could adapters could be made for other Go SQLite bindings in
the future.

### Beyond aggregation

This standard library I published doesn't just include additional
aggregation functions.

#### Date parsing

The library includes best-effort date parsing/retrieval functions.

![Date parsing functions](/0.11.0-stdlib-date.png)

#### URL parsing

It includes URL parsing/retrieval functions.

![URL parsing functions](/0.11.0-stdlib-url.png)

#### String functions

It includes string functions.

![String parsing functions](/0.11.0-stdlib-strings.png)

#### Hashing/encoding functions

It includes hashing and encoding/decoding functions.

![String parsing functions](/0.11.0-stdlib-encoding.png)

#### Math functions

And it includes math functions that are largely ports of SQLite's
["builtin" math
functions](https://www.sqlite.org/lang_mathfunc.html). The thing is
that these functions are disabled by default. Easier to just provide
them in Go in this library.

![Math functions](/0.11.0-stdlib-math.png)

### Conclusion

With this standard library, SQL exploration of ad-hoc datasets in
DataStation and dsq are significantly more convenient.

Check out the [library
README](https://github.com/multiprocessio/go-sqlite3-stdlib) for full
docs.

SQLite is amazing software. But it's probably worth adding this
limited list of builtin functions to your "things to consider" when
deciding whether SQLite is right for you. Its much smaller than I
expected, personally. So you may need to do some work to fill in the
gaps (if you aren't embedding SQLite in Go).

#### Share

<blockquote class="twitter-tweet"><p lang="en" dir="ltr">I wrote a short post about SQLite&#39;s surprisingly limited builtin functions (surprising to me anyway; compared to DuckDB and PostgreSQL) and how I worked around that in a Go library for <a href="https://twitter.com/multiprocessio?ref_src=twsrc%5Etfw">@multiprocessio</a> DataStation/dsq.<a href="https://t.co/wiDp0P9pdl">https://t.co/wiDp0P9pdl</a> <a href="https://t.co/pi7Z5ePd97">pic.twitter.com/pi7Z5ePd97</a></p>&mdash; Phil Eaton (@phil_eaton) <a href="https://twitter.com/phil_eaton/status/1561457805143511040?ref_src=twsrc%5Etfw">August 21, 2022</a></blockquote> <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>
{% endblock %}
