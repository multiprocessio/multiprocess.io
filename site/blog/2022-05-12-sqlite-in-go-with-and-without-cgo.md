{% extends "blog/layout.tmpl" %}

{% block postTitle %}SQLite in Go, with and without cgo{% endblock %}
{% block postDate %}May 12, 2022{% endblock %}
{% block postAuthor %}Phil Eaton{% endblock %}
{% block postAuthorEmail %}phil@multiprocess.io{% endblock %}
{% block postTags %}sqlite,go,benchmark{% endblock %}

{% block postBody %}
Most people use the
[mattn/go-sqlite3](https://github.com/mattn/go-sqlite3) package to interact with SQLite in Go. This
package uses cgo and bundles the [SQLite C amalgamation
files](https://github.com/mattn/go-sqlite3/commit/2df077b74c66723d9b44d01c8db88e74191bdd0e)
with the Go source.

But Go developers often prefer not to use cgo (see for example [cgo is
not go](https://dave.cheney.net/tag/cgo)). I mention this because
there happens to be an underrated [translation of SQLite's C source
code to Go](https://gitlab.com/cznic/sqlite). Since it is a
translation of C to Go, you don't need to use cgo to call into
it. Some developers find this idea compelling. And this Go translation
is an impressive work in and of itself.

But for real-world usage there are at least two major concerns I had:
compatibility and performance. According to [their
documentation](https://pkg.go.dev/modernc.org/sqlite#section-readme)
they pass most or all SQLite3 tests, so it seems pretty compatible. But I
didn't see anything on their site or documentation (which, to their detriment,
is pretty scant) that talked about performance. So I took a look.

This post summarizes some basic ingestion and query benchmarks using
[mattn/go-sqlite3](https://github.com/mattn/go-sqlite3) and
[modernc.org/sqlite](https://pkg.go.dev/modernc.org/sqlite). tldr; the
Go translation is between twice as slow and 10% slower for both small
datasets and large, for `INSERT`s and `SELECT`s.

# Benchmarks

There are two main benchmarks, one ingest benchmark and one query
benchmark. They are both run 10 times and both run against a growing
number of rows.

## Ingest

This benchmark inserts 10_000, 479_827, and 4_798_270 rows 10 times
each. There are ten columns and the contents are a mix of randomly
generated strings and integers.

## Query

This benchmark runs a single `GROUP BY` query: `SELECT COUNT(1), age
FROM people GROUP BY age ORDER BY COUNT(1) DESC`. It runs 10 times
against each of the sizes of rows ingested.

## Code

Here is the [mattn/go-sqlite3
version](https://github.com/multiprocessio/sqlite-cgo-no-cgo/blob/main/cgo/main.go). And here is the [SQLite Go translated
version](https://github.com/multiprocessio/sqlite-cgo-no-cgo/blob/main/nocgo/main.go).

## Machine Specs

I am running these benchmarks on a dedicated bare metal instance, [OVH
Rise-1](https://us.ovhcloud.com/bare-metal/rise/rise-1/).

* RAM: 64 GB DDR4 ECC 2,133 MHz
* Disk: 2x450 GB SSD NVMe in Soft RAID
* Processor: Intel Xeon E3-1230v6 - 4c/8t - 3.5 GHz/3.9 GHz

# Results

Below are the averages across all 10 runs for each query category,
number of rows acting on, and the library (cgo or no cgo) used.

<table class="table table-bordered table-hover table-condensed">
<thead><tr><th title="Field #1">Category</th>
<th title="Field #2">Average Time (Seconds)</th>
<th title="Field #3">Standard Deviation</th>
<th title="Field #4"># Rows</th>
<th title="Field #5">Library</th>
</tr></thead>
<tbody><tr>
<td>insert</td>
<td>0.0446901</td>
<td>0.000986</td>
<td>10000</td>
<td>mattn</td>
</tr>
<tr>
<td>insert</td>
<td>0.0954987</td>
<td>0.0018</td>
<td>10000</td>
<td>modernc</td>
</tr>
<tr>
<td>group_by</td>
<td>0.0028469</td>
<td>0.000132</td>
<td>10000</td>
<td>mattn</td>
</tr>
<tr>
<td>group_by</td>
<td>0.0045523</td>
<td>.000085</td>
<td>10000</td>
<td>modernc</td>
</tr>
<tr>
<td>insert</td>
<td>2.317502</td>
<td>0.017499</td>
<td>479827</td>
<td>mattn</td>
</tr>
<tr>
<td>insert</td>
<td>4.6066586</td>
<td>0.027994</td>
<td>479827</td>
<td>modernc</td>
</tr>
<tr>
<td>group_by</td>
<td>0.227473</td>
<td>0.005689</td>
<td>479827</td>
<td>mattn</td>
</tr>
<tr>
<td>group_by</td>
<td>0.2786216</td>
<td>0.00188</td>
<td>479827</td>
<td>modernc</td>
</tr>
<tr>
<td>insert</td>
<td>23.0529852</td>
<td>0.077669</td>
<td>4798270</td>
<td>mattn</td>
</tr>
<tr>
<td>insert</td>
<td>46.2240191</td>
<td>0.370401</td>
<td>4798270</td>
<td>modernc</td>
</tr>
<tr>
<td>group_by</td>
<td>3.5935438</td>
<td>0.052308</td>
<td>4798270</td>
<td>mattn</td>
</tr>
<tr>
<td>group_by</td>
<td>4.0170164</td>
<td>0.066636</td>
<td>4798270</td>
<td>modernc</td>
</tr>
</tbody></table>

# Summary

[modernc.org/sqlite](https://gitlab.com/cznic/sqlite) is a very
impressive project. But the Go translation is twice as slow in
`INSERT`s. It does quite well with `SELECT`s for a translation; being
between 10% slower and at worst twice as slow.

Based on these results, if your workload has solely small datasets
(i.e. small business apps) the tradeoff allowing you to avoid cgo
could be worth it. Otherwise if you care strongly about performance
you'll be better off with the real SQLite and
[mattn/go-sqlite3](https://github.com/mattn/go-sqlite3).

## Errata: bug in SELECT

Thanks
[benhoyt](https://www.reddit.com/r/golang/comments/uo5mix/comment/i8dnkb0/)
and [oefrha](https://news.ycombinator.com/item?id=31366759) for
finding a bug in the `SELECT` query that was causing the mattn version
not to finish executing the `SELECT` query.

<details>
  <summary>Summary before errata correction</summary>
<span>

[modernc.org/sqlite](https://gitlab.com/cznic/sqlite) is a very
impressive project. But it is at least twice as slow in every
variation even with smaller datasets. And `SELECT` performance gets
way worse as the dataset size increases. The Go translation also has a
greater standard deviation which might be attributable to the garbage
collector. My guess is that mattn/go-sqlite3 is so constant in
`SELECT` performance even as the dataset increases because even 4
million rows is peanuts for SQLite. Or maybe my benchmark code is wrong!

Based on these results, if your workload has solely small datasets
(i.e. small business apps) the tradeoff allowing you to avoid cgo
could be worth it. Otherwise if you care strongly about performance
you'll be better off with the real SQLite and
[mattn/go-sqlite3](https://github.com/mattn/go-sqlite3).
</span>
</details>

#### Share

<blockquote class="twitter-tweet"><p lang="en" dir="ltr">Did you know there is a Go translation of SQLite&#39;s C source code? This translation allows you to use SQLite in Go without cgo, which many Go developers find enticing.<br><br>But how does it perform? Unfortunately, at least twice as slow in all tested cases.<a href="https://t.co/rgarrMJFKQ">https://t.co/rgarrMJFKQ</a> <a href="https://t.co/UzDO9BU371">pic.twitter.com/UzDO9BU371</a></p>&mdash; Multiprocess Labs (@multiprocessio) <a href="https://twitter.com/multiprocessio/status/1524795230188347393?ref_src=twsrc%5Etfw">May 12, 2022</a></blockquote> <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>

{% endblock %}
