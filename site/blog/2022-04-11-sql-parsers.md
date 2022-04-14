{% extends "blog/layout.tmpl" %}

{% block postTitle %}Surveying SQL parser libraries in a few high-level languages{% endblock %}
{% block postDate %}April 11, 2022{% endblock %}
{% block postAuthor %}Phil Eaton{% endblock %}
{% block postAuthorEmail %}phil@multiprocess.io{% endblock %}
{% block postTags %}sql,parsing,go,rust,java,python,ruby,javascript{% endblock %}

{% block postBody %}
This post surveys 10+ SQL parsing libraries in Ruby, Java, Rust, Python,
JavaScript, and Go. Two of them,
[go-mysql-server](https://github.com/dolthub/go-mysql-server) and
[sqlparser-rs](https://github.com/sqlparser-rs/sqlparser-rs), have
handwritten parsers. The rest use parser generators.

This post will look at support for a few basic `SELECT` queries and
the usefulness of error messages. SQL is really complex though. So
keep in mind it takes a lot of work to build these systems and
the authors deserve a ton of credit.

This post is not an exhaustive list of parser libraries. But these ones
alone took me a while to find. If there are other major libraries I
missed feel free to send me them! If there are enough I may make a
second post.

All code for this post is [available on Github](https://github.com/multiprocessio/sql-parsers).

## Sample queries

SQL is such a large standard it's going to be hard to express large
parts of it. It's also hard to test "SQL parsers" because there are a
few major SQL dialects. And I'm only going to stick to the "free"
SQLs. MySQL notably diverges from the SQL standard by using backticks for columns and single or double quotes
for strings. MySQL, PostgreSQL, and
SQLite all have different ways of expressing dates, date
calculcations, and intervals.

In trying to avoid some of these contentious parts of SQL we'll be
eliminating large parts of very commonly used code. Almost every
real-world query involves dates.

We're also only going to test `SELECT` statements. So missing cases
will be on you to test.

Caveats out of the way, here are the three syntactically valid and one
syntactically invalid queries we'll try out.

One simple one:

```sql
SELECT * FROM x WHERE y > 9 ORDER BY z LIMIT 5
```

One less simple one:

```sql
SELECT COUNT(1) AS count, name section FROM (SELECT * FROM jobs) t GROUP BY name LIMIT 10
```

One complex one:

```sql
SELECT
	country.country_name_eng,
	SUM(CASE WHEN talk.id IS NOT NULL THEN 1 ELSE 0 END) AS talks,
	AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) AS avg_difference
FROM country
LEFT JOIN city ON city.country_id = country.id
LEFT JOIN customer ON city.id = customer.city_id
LEFT JOIN talk ON talk.customer_id = customer.id
GROUP BY
	country.id,
	country.country_name_eng
HAVING AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) > (SELECT AVG(DATEDIFF(SECOND, talk.start_time, talk.end_time)) FROM talk)
ORDER BY talks DESC, country.id ASC;
```

And one incorrect one (missing table name):

```sql
SELECT * FROM GROUP BY age
```

## Go

### DoltHub's go-mysql-server

[This repo](https://github.com/dolthub/go-mysql-server) is a fork of src-d/go-mysql-server after src-d shut
down. It's not just a SQL parser, it's an entire SQL engine. You can
read about why DoltHub adopted it
[here](https://www.dolthub.com/blog/2020-05-04-adopting-go-mysql-server/). But
the engine exposes a SQL parser, so we're going to look at that. The SQL parser is [handwritten](https://github.com/dolthub/go-mysql-server/blob/main/sql/parse/parse.go).

#### Setup

Create a new directory, set up go mod with `go mod init test`, and enter the following into `main.go`:

```go
package main

import (
	"fmt"

	"github.com/dolthub/go-mysql-server/sql"
	"github.com/dolthub/go-mysql-server/sql/parse"
	"github.com/kr/pretty"
)

func main() {
	simple := "SELECT * FROM x WHERE y > 9 ORDER BY z LIMIT 5"

	medium := "SELECT COUNT(1) AS count, name section FROM (SELECT * FROM jobs) t GROUP BY name LIMIT 10"

	complex := `
SELECT
	country.country_name_eng,
	SUM(CASE WHEN talk.id IS NOT NULL THEN 1 ELSE 0 END) AS talks,
	AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) AS avg_difference
FROM country
LEFT JOIN city ON city.country_id = country.id
LEFT JOIN customer ON city.id = customer.city_id
LEFT JOIN talk ON talk.customer_id = customer.id
GROUP BY
	country.id,
	country.country_name_eng
HAVING AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) > (SELECT AVG(DATEDIFF(SECOND, talk.start_time, talk.end_time)) FROM talk)
ORDER BY talks DESC, country.id ASC;
`

	simplebad := "SELECT * FROM GROUP BY age"

	for _,  test := range []string{simple, medium, complex, simplebad} {
		ast, err := parse.Parse(sql.NewEmptyContext(), test)
		if err != nil {
			fmt.Println(err)
			continue
		}

		fmt.Println(pretty.Sprint(ast))
	}
}
```

(The `kr/pretty` repo is just so that we can dump the AST to stdout in a somewhat readable form.)

Now run `go mod tidy` and `go run main.go` and notice:

```go
&plan.Project{
    UnaryNode: plan.UnaryNode{
        Child: &plan.UnresolvedTable{
            name:     "x",
            Database: "",
            AsOf:     nil,
        },
    },
    Projections: {
        &expression.Star{},
    },
}
&plan.Limit{
    UnaryNode: plan.UnaryNode{
        Child: &plan.GroupBy{
            UnaryNode: plan.UnaryNode{
                Child: &plan.UnresolvedTable{
                    name:     "t",
                    Database: "",
                    AsOf:     nil,
                },
            },
            SelectedExprs: {
                &expression.Alias{
                    UnaryExpression: expression.UnaryExpression{
                        Child: &expression.UnresolvedFunction{
                            name:        "count",
                            IsAggregate: true,
                            Window:      (*sql.Window)(nil),
                            Arguments:   {
                                &expression.Literal{
                                    value:     int8(1),
                                    fieldType: sql.numberTypeImpl{baseType:257},
                                },
                            },
                        },
                    },
                    name: "count",
                },
                &expression.Alias{
                    UnaryExpression: expression.UnaryExpression{
                        Child: &expression.UnresolvedColumn{name:"name", table:""},
                    },
                    name: "section",
                },
            },
            GroupByExprs: {
                &expression.UnresolvedColumn{name:"name", table:""},
            },
        },
    },
    Limit: &expression.Literal{
        value:     int8(10),
        fieldType: sql.numberTypeImpl{baseType:257},
    },
    CalcFoundRows: false,
}
&plan.Sort{
    UnaryNode: plan.UnaryNode{
        Child: &plan.Having{
            UnaryNode: plan.UnaryNode{
                Child: &plan.GroupBy{
                    UnaryNode: plan.UnaryNode{
                        Child: &plan.LeftJoin{
                            joinStruct: plan.joinStruct{
                                BinaryNode: plan.BinaryNode{
                                    left: &plan.LeftJoin{
                                        joinStruct: plan.joinStruct{
                                            BinaryNode: plan.BinaryNode{
                                                left: &plan.LeftJoin{
                                                    joinStruct: plan.joinStruct{
                                                        BinaryNode: plan.BinaryNode{
                                                            left: &plan.UnresolvedTable{
                                                                name:     "country",
                                                                Database: "",
                                                                AsOf:     nil,
                                                            },
                                                            right: &plan.UnresolvedTable{
                                                                name:     "city",
                                                                Database: "",
                                                                AsOf:     nil,
                                                            },
                                                        },
                                                        Cond: &expression.Equals{
                                                            comparison: expression.comparison{
                                                                BinaryExpression: expression.BinaryExpression{
                                                                    Left:  &expression.UnresolvedColumn{name:"country_id", table:"city"},
                                                                    Right: &expression.UnresolvedColumn{name:"id", table:"country"},
                                                                },
                                                            },
                                                        },
                                                        CommentStr: "",
                                                        ScopeLen:   0,
                                                        JoinMode:   0x0,
                                                    },
                                                },
                                                right: &plan.UnresolvedTable{
                                                    name:     "customer",
                                                    Database: "",
                                                    AsOf:     nil,
                                                },
                                            },
                                            Cond: &expression.Equals{
                                                comparison: expression.comparison{
                                                    BinaryExpression: expression.BinaryExpression{
                                                        Left:  &expression.UnresolvedColumn{name:"id", table:"city"},
                                                        Right: &expression.UnresolvedColumn{name:"city_id", table:"customer"},
                                                    },
                                                },
                                            },
                                            CommentStr: "",
                                            ScopeLen:   0,
                                            JoinMode:   0x0,
                                        },
                                    },
                                    right: &plan.UnresolvedTable{
                                        name:     "talk",
                                        Database: "",
                                        AsOf:     nil,
                                    },
                                },
                                Cond: &expression.Equals{
                                    comparison: expression.comparison{
                                        BinaryExpression: expression.BinaryExpression{
                                            Left:  &expression.UnresolvedColumn{name:"customer_id", table:"talk"},
                                            Right: &expression.UnresolvedColumn{name:"id", table:"customer"},
                                        },
                                    },
                                },
                                CommentStr: "",
                                ScopeLen:   0,
                                JoinMode:   0x0,
                            },
                        },
                    },
                    SelectedExprs: {
                        &expression.UnresolvedColumn{name:"country_name_eng", table:"country"},
                        &expression.Alias{
                            UnaryExpression: expression.UnaryExpression{
                                Child: &expression.UnresolvedFunction{
                                    name:        "sum",
                                    IsAggregate: true,
                                    Window:      (*sql.Window)(nil),
                                    Arguments:   {
                                        &expression.Case{
                                            Expr:     nil,
                                            Branches: {
                                                {
                                                    Cond: &expression.Not{
                                                        UnaryExpression: expression.UnaryExpression{
                                                            Child: &expression.IsNull{
                                                                UnaryExpression: expression.UnaryExpression{
                                                                    Child: &!%v(DEPTH EXCEEDED),
                                                                },
                                                            },
                                                        },
                                                    },
                                                    Value: &expression.Literal{
                                                        value:     int8(1),
                                                        fieldType: sql.numberTypeImpl{baseType:257},
                                                    },
                                                },
                                            },
                                            Else: &expression.Literal{
                                                value:     int8(0),
                                                fieldType: sql.numberTypeImpl{baseType:257},
                                            },
                                        },
                                    },
                                },
                            },
                            name: "talks",
                        },
                        &expression.Alias{
                            UnaryExpression: expression.UnaryExpression{
                                Child: &expression.UnresolvedFunction{
                                    name:        "avg",
                                    IsAggregate: true,
                                    Window:      (*sql.Window)(nil),
                                    Arguments:   {
                                        &expression.UnresolvedFunction{
                                            name:        "isnull",
                                            IsAggregate: false,
                                            Window:      (*sql.Window)(nil),
                                            Arguments:   {
                                                &expression.UnresolvedFunction{
                                                    name:        "datediff",
                                                    IsAggregate: false,
                                                    Window:      (*sql.Window)(nil),
                                                    Arguments:   {
                                                        !%v(DEPTH EXCEEDED),
                                                        !%v(DEPTH EXCEEDED),
                                                        !%v(DEPTH EXCEEDED),
                                                    },
                                                },
                                                &expression.Literal{
                                                    value:     int8(0),
                                                    fieldType: sql.numberTypeImpl{baseType:257},
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                            name: "avg_difference",
                        },
                    },
                    GroupByExprs: {
                        &expression.UnresolvedColumn{name:"id", table:"country"},
                        &expression.UnresolvedColumn{name:"country_name_eng", table:"country"},
                    },
                },
            },
            Cond: &expression.GreaterThan{
                comparison: expression.comparison{
                    BinaryExpression: expression.BinaryExpression{
                        Left: &expression.UnresolvedFunction{
                            name:        "avg",
                            IsAggregate: true,
                            Window:      (*sql.Window)(nil),
                            Arguments:   {
                                &expression.UnresolvedFunction{
                                    name:        "isnull",
                                    IsAggregate: false,
                                    Window:      (*sql.Window)(nil),
                                    Arguments:   {
                                        &expression.UnresolvedFunction{
                                            name:        "datediff",
                                            IsAggregate: false,
                                            Window:      (*sql.Window)(nil),
                                            Arguments:   {
                                                &expression.UnresolvedColumn{name:"SECOND", table:""},
                                                &expression.UnresolvedColumn{name:"start_time", table:"talk"},
                                                &expression.UnresolvedColumn{name:"end_time", table:"talk"},
                                            },
                                        },
                                        &expression.Literal{
                                            value:     int8(0),
                                            fieldType: sql.numberTypeImpl{baseType:257},
                                        },
                                    },
                                },
                            },
                        },
                        Right: &plan.Subquery{
                            Query: &plan.GroupBy{
                                UnaryNode: plan.UnaryNode{
                                    Child: &plan.UnresolvedTable{
                                        name:     "talk",
                                        Database: "",
                                        AsOf:     nil,
                                    },
                                },
                                SelectedExprs: {
                                    &expression.Alias{
                                        UnaryExpression: expression.UnaryExpression{
                                            Child: &expression.UnresolvedFunction{
                                                name:        "avg",
                                                IsAggregate: true,
                                                Window:      (*sql.Window)(nil),
                                                Arguments:   {
                                                    &expression.UnresolvedFunction{
                                                        name:        "datediff",
                                                        IsAggregate: false,
                                                        Window:      (*sql.Window)(nil),
                                                        Arguments:   {
                                                            !%v(DEPTH EXCEEDED),
                                                            !%v(DEPTH EXCEEDED),
                                                            !%v(DEPTH EXCEEDED),
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                        name: "AVG(DATEDIFF(SECOND, talk.start_time, talk.end_time))",
                                    },
                                },
                                GroupByExprs: {
                                },
                            },
                            QueryString:     "select AVG(DATEDIFF(SECOND, talk.start_time, talk.end_time)) from talk",
                            canCacheResults: false,
                            resultsCached:   false,
                            cache:           nil,
                            hashCache:       nil,
                            disposeFunc:     sql.DisposeFunc {...},
                            cacheMu:         sync.Mutex{},
                        },
                    },
                },
            },
        },
    },
    SortFields: {
        {
            Column:       &expression.UnresolvedColumn{name:"talks", table:""},
            Order:        0x2,
            NullOrdering: 0x0,
        },
        {
            Column:       &expression.UnresolvedColumn{name:"id", table:"country"},
            Order:        0x1,
            NullOrdering: 0x0,
        },
    },
}
syntax error at position 20 near 'GROUP'
```

The error:

```
syntax error at position 20 near 'GROUP'
```

Pretty good! The error message is not great though. It would be better
if they included line number and column rather than position (which is
presumably character index into the string or token index into the
lexed tokens). And it would be better if it explained what it was
expecting at the position.

But overall not bad!

### Vitess's parser

[Vitess](https://github.com/vitessio/vitess) is a SQL scaling layer
for use in front of MySQL servers, originally developed by Youtube. It
is now part of the Cloud Native Computing Foundation. You can read
more about it
[here](https://vitess.io/docs/13.0/overview/history/). Like
go-mysql-server it happens to include a custom SQL parser. The SQL
parser is [not
handwritten](https://github.com/vitessio/vitess/tree/main/go/vt/sqlparser)
but uses goyacc.

Let's try it out.

#### Setup

Create a new directory, set up go mod with `go mod init test`, and
enter the following into `main.go`:

```go
package main

import (
	"fmt"

	"vitess.io/vitess/go/vt/sqlparser"
	"github.com/kr/pretty"
)

func main() {
	simple := "SELECT * FROM x"

	medium := "SELECT COUNT(1) AS count, name section FROM t GROUP BY name LIMIT 10"

	complex := `
SELECT
	country.country_name_eng,
	SUM(CASE WHEN talk.id IS NOT NULL THEN 1 ELSE 0 END) AS talks,
	AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) AS avg_difference
FROM country
LEFT JOIN city ON city.country_id = country.id
LEFT JOIN customer ON city.id = customer.city_id
LEFT JOIN talk ON talk.customer_id = customer.id
GROUP BY
	country.id,
	country.country_name_eng
HAVING AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) > (SELECT AVG(DATEDIFF(SECOND, talk.start_time, talk.end_time)) FROM talk)
ORDER BY talks DESC, country.id ASC;
`

	simplebad := "SELECT * FROM GROUP BY age"

	for _,  test := range []string{simple, medium, complex, simplebad} {
		ast, _, err := sqlparser.Parse2(test)
		if err != nil {
			fmt.Println(err)
			continue
		}

		fmt.Println(pretty.Sprint(ast))
	}
}
```

Now run `go mod tidy` and `go run main.go`:

```go
&sqlparser.Select{
    Cache:            (*bool)(nil),
    Distinct:         false,
    StraightJoinHint: false,
    SQLCalcFoundRows: false,
    From:             {
        &sqlparser.AliasedTableExpr{
            Expr: sqlparser.TableName{
                Name:      sqlparser.TableIdent{v:"x"},
                Qualifier: sqlparser.TableIdent{},
            },
            Partitions: nil,
            As:         sqlparser.TableIdent{},
            Hints:      (*sqlparser.IndexHints)(nil),
            Columns:    nil,
        },
    },
    Comments:    nil,
    SelectExprs: {
        &sqlparser.StarExpr{},
    },
    Where:   (*sqlparser.Where)(nil),
    With:    (*sqlparser.With)(nil),
    GroupBy: nil,
    Having:  (*sqlparser.Where)(nil),
    OrderBy: nil,
    Limit:   (*sqlparser.Limit)(nil),
    Lock:    0,
    Into:    (*sqlparser.SelectInto)(nil),
}
&sqlparser.Select{
    Cache:            (*bool)(nil),
    Distinct:         false,
    StraightJoinHint: false,
    SQLCalcFoundRows: false,
    From:             {
        &sqlparser.AliasedTableExpr{
            Expr: sqlparser.TableName{
                Name:      sqlparser.TableIdent{v:"t"},
                Qualifier: sqlparser.TableIdent{},
            },
            Partitions: nil,
            As:         sqlparser.TableIdent{},
            Hints:      (*sqlparser.IndexHints)(nil),
            Columns:    nil,
        },
    },
    Comments:    nil,
    SelectExprs: {
        &sqlparser.AliasedExpr{
            Expr: &sqlparser.FuncExpr{
                Qualifier: sqlparser.TableIdent{},
                Name:      sqlparser.ColIdent{
                    _:  {
                    },
                    val:     "COUNT",
                    lowered: "",
                    at:      0,
                },
                Distinct: false,
                Exprs:    {
                    &sqlparser.AliasedExpr{
                        Expr: &sqlparser.Literal{Type:1, Val:"1"},
                        As:   sqlparser.ColIdent{},
                    },
                },
            },
            As: sqlparser.ColIdent{
                _:  {
                },
                val:     "count",
                lowered: "",
                at:      0,
            },
        },
        &sqlparser.AliasedExpr{
            Expr: &sqlparser.ColName{
                Metadata: nil,
                Name:     sqlparser.ColIdent{
                    _:  {
                    },
                    val:     "name",
                    lowered: "",
                    at:      0,
                },
                Qualifier: sqlparser.TableName{},
            },
            As: sqlparser.ColIdent{
                _:  {
                },
                val:     "section",
                lowered: "",
                at:      0,
            },
        },
    },
    Where:   (*sqlparser.Where)(nil),
    With:    (*sqlparser.With)(nil),
    GroupBy: {
        &sqlparser.ColName{
            Metadata: nil,
            Name:     sqlparser.ColIdent{
                _:  {
                },
                val:     "name",
                lowered: "",
                at:      0,
            },
            Qualifier: sqlparser.TableName{},
        },
    },
    Having:  (*sqlparser.Where)(nil),
    OrderBy: nil,
    Limit:   &sqlparser.Limit{
        Offset:   nil,
        Rowcount: &sqlparser.Literal{Type:1, Val:"10"},
    },
    Lock: 0,
    Into: (*sqlparser.SelectInto)(nil),
}
&sqlparser.Select{
    Cache:            (*bool)(nil),
    Distinct:         false,
    StraightJoinHint: false,
    SQLCalcFoundRows: false,
    From:             {
        &sqlparser.JoinTableExpr{
            LeftExpr: &sqlparser.JoinTableExpr{
                LeftExpr: &sqlparser.JoinTableExpr{
                    LeftExpr: &sqlparser.AliasedTableExpr{
                        Expr: sqlparser.TableName{
                            Name:      sqlparser.TableIdent{v:"country"},
                            Qualifier: sqlparser.TableIdent{},
                        },
                        Partitions: nil,
                        As:         sqlparser.TableIdent{},
                        Hints:      (*sqlparser.IndexHints)(nil),
                        Columns:    nil,
                    },
                    Join:      2,
                    RightExpr: &sqlparser.AliasedTableExpr{
                        Expr: sqlparser.TableName{
                            Name:      sqlparser.TableIdent{v:"city"},
                            Qualifier: sqlparser.TableIdent{},
                        },
                        Partitions: nil,
                        As:         sqlparser.TableIdent{},
                        Hints:      (*sqlparser.IndexHints)(nil),
                        Columns:    nil,
                    },
                    Condition: &sqlparser.JoinCondition{
                        On: &sqlparser.ComparisonExpr{
                            Operator: 0,
                            Left:     &sqlparser.ColName{
                                Metadata: nil,
                                Name:     sqlparser.ColIdent{
                                    _:  {
                                    },
                                    val:     "country_id",
                                    lowered: "",
                                    at:      0,
                                },
                                Qualifier: sqlparser.TableName{
                                    Name:      sqlparser.TableIdent{v:"city"},
                                    Qualifier: sqlparser.TableIdent{},
                                },
                            },
                            Right: &sqlparser.ColName{
                                Metadata: nil,
                                Name:     sqlparser.ColIdent{
                                    _:  {
                                    },
                                    val:     "id",
                                    lowered: "",
                                    at:      0,
                                },
                                Qualifier: sqlparser.TableName{
                                    Name:      sqlparser.TableIdent{v:"country"},
                                    Qualifier: sqlparser.TableIdent{},
                                },
                            },
                            Escape: nil,
                        },
                        Using: nil,
                    },
                },
                Join:      2,
                RightExpr: &sqlparser.AliasedTableExpr{
                    Expr: sqlparser.TableName{
                        Name:      sqlparser.TableIdent{v:"customer"},
                        Qualifier: sqlparser.TableIdent{},
                    },
                    Partitions: nil,
                    As:         sqlparser.TableIdent{},
                    Hints:      (*sqlparser.IndexHints)(nil),
                    Columns:    nil,
                },
                Condition: &sqlparser.JoinCondition{
                    On: &sqlparser.ComparisonExpr{
                        Operator: 0,
                        Left:     &sqlparser.ColName{
                            Metadata: nil,
                            Name:     sqlparser.ColIdent{
                                _:  {
                                },
                                val:     "id",
                                lowered: "",
                                at:      0,
                            },
                            Qualifier: sqlparser.TableName{
                                Name:      sqlparser.TableIdent{v:"city"},
                                Qualifier: sqlparser.TableIdent{},
                            },
                        },
                        Right: &sqlparser.ColName{
                            Metadata: nil,
                            Name:     sqlparser.ColIdent{
                                _:  {
                                },
                                val:     "city_id",
                                lowered: "",
                                at:      0,
                            },
                            Qualifier: sqlparser.TableName{
                                Name:      sqlparser.TableIdent{v:"customer"},
                                Qualifier: sqlparser.TableIdent{},
                            },
                        },
                        Escape: nil,
                    },
                    Using: nil,
                },
            },
            Join:      2,
            RightExpr: &sqlparser.AliasedTableExpr{
                Expr: sqlparser.TableName{
                    Name:      sqlparser.TableIdent{v:"talk"},
                    Qualifier: sqlparser.TableIdent{},
                },
                Partitions: nil,
                As:         sqlparser.TableIdent{},
                Hints:      (*sqlparser.IndexHints)(nil),
                Columns:    nil,
            },
            Condition: &sqlparser.JoinCondition{
                On: &sqlparser.ComparisonExpr{
                    Operator: 0,
                    Left:     &sqlparser.ColName{
                        Metadata: nil,
                        Name:     sqlparser.ColIdent{
                            _:  {
                            },
                            val:     "customer_id",
                            lowered: "",
                            at:      0,
                        },
                        Qualifier: sqlparser.TableName{
                            Name:      sqlparser.TableIdent{v:"talk"},
                            Qualifier: sqlparser.TableIdent{},
                        },
                    },
                    Right: &sqlparser.ColName{
                        Metadata: nil,
                        Name:     sqlparser.ColIdent{
                            _:  {
                            },
                            val:     "id",
                            lowered: "",
                            at:      0,
                        },
                        Qualifier: sqlparser.TableName{
                            Name:      sqlparser.TableIdent{v:"customer"},
                            Qualifier: sqlparser.TableIdent{},
                        },
                    },
                    Escape: nil,
                },
                Using: nil,
            },
        },
    },
    Comments:    nil,
    SelectExprs: {
        &sqlparser.AliasedExpr{
            Expr: &sqlparser.ColName{
                Metadata: nil,
                Name:     sqlparser.ColIdent{
                    _:  {
                    },
                    val:     "country_name_eng",
                    lowered: "",
                    at:      0,
                },
                Qualifier: sqlparser.TableName{
                    Name:      sqlparser.TableIdent{v:"country"},
                    Qualifier: sqlparser.TableIdent{},
                },
            },
            As: sqlparser.ColIdent{},
        },
        &sqlparser.AliasedExpr{
            Expr: &sqlparser.FuncExpr{
                Qualifier: sqlparser.TableIdent{},
                Name:      sqlparser.ColIdent{
                    _:  {
                    },
                    val:     "SUM",
                    lowered: "",
                    at:      0,
                },
                Distinct: false,
                Exprs:    {
                    &sqlparser.AliasedExpr{
                        Expr: &sqlparser.CaseExpr{
                            Expr:  nil,
                            Whens: {
                                &sqlparser.When{
                                    Cond: &sqlparser.IsExpr{
                                        Left: &sqlparser.ColName{
                                            Metadata: nil,
                                            Name:     sqlparser.ColIdent{
                                                _:  {
                                                },
                                                val:     "id",
                                                lowered: "",
                                                at:      0,
                                            },
                                            Qualifier: sqlparser.TableName{
                                                Name:      sqlparser.TableIdent{v:"talk"},
                                                Qualifier: sqlparser.TableIdent{},
                                            },
                                        },
                                        Right: 1,
                                    },
                                    Val: &sqlparser.Literal{Type:1, Val:"1"},
                                },
                            },
                            Else: &sqlparser.Literal{Type:1, Val:"0"},
                        },
                        As: sqlparser.ColIdent{},
                    },
                },
            },
            As: sqlparser.ColIdent{
                _:  {
                },
                val:     "talks",
                lowered: "",
                at:      0,
            },
        },
        &sqlparser.AliasedExpr{
            Expr: &sqlparser.FuncExpr{
                Qualifier: sqlparser.TableIdent{},
                Name:      sqlparser.ColIdent{
                    _:  {
                    },
                    val:     "AVG",
                    lowered: "",
                    at:      0,
                },
                Distinct: false,
                Exprs:    {
                    &sqlparser.AliasedExpr{
                        Expr: &sqlparser.FuncExpr{
                            Qualifier: sqlparser.TableIdent{},
                            Name:      sqlparser.ColIdent{
                                _:  {
                                },
                                val:     "ISNULL",
                                lowered: "",
                                at:      0,
                            },
                            Distinct: false,
                            Exprs:    {
                                &sqlparser.AliasedExpr{
                                    Expr: &sqlparser.FuncExpr{
                                        Qualifier: sqlparser.TableIdent{},
                                        Name:      sqlparser.ColIdent{
                                            _:  {
                                            },
                                            val:     "DATEDIFF",
                                            lowered: "",
                                            at:      0,
                                        },
                                        Distinct: false,
                                        Exprs:    {
                                            !%v(DEPTH EXCEEDED),
                                            !%v(DEPTH EXCEEDED),
                                            !%v(DEPTH EXCEEDED),
                                        },
                                    },
                                    As: sqlparser.ColIdent{},
                                },
                                &sqlparser.AliasedExpr{
                                    Expr: &sqlparser.Literal{Type:1, Val:"0"},
                                    As:   sqlparser.ColIdent{},
                                },
                            },
                        },
                        As: sqlparser.ColIdent{},
                    },
                },
            },
            As: sqlparser.ColIdent{
                _:  {
                },
                val:     "avg_difference",
                lowered: "",
                at:      0,
            },
        },
    },
    Where:   (*sqlparser.Where)(nil),
    With:    (*sqlparser.With)(nil),
    GroupBy: {
        &sqlparser.ColName{
            Metadata: nil,
            Name:     sqlparser.ColIdent{
                _:  {
                },
                val:     "id",
                lowered: "",
                at:      0,
            },
            Qualifier: sqlparser.TableName{
                Name:      sqlparser.TableIdent{v:"country"},
                Qualifier: sqlparser.TableIdent{},
            },
        },
        &sqlparser.ColName{
            Metadata: nil,
            Name:     sqlparser.ColIdent{
                _:  {
                },
                val:     "country_name_eng",
                lowered: "",
                at:      0,
            },
            Qualifier: sqlparser.TableName{
                Name:      sqlparser.TableIdent{v:"country"},
                Qualifier: sqlparser.TableIdent{},
            },
        },
    },
    Having: &sqlparser.Where{
        Type: 1,
        Expr: &sqlparser.ComparisonExpr{
            Operator: 2,
            Left:     &sqlparser.FuncExpr{
                Qualifier: sqlparser.TableIdent{},
                Name:      sqlparser.ColIdent{
                    _:  {
                    },
                    val:     "AVG",
                    lowered: "",
                    at:      0,
                },
                Distinct: false,
                Exprs:    {
                    &sqlparser.AliasedExpr{
                        Expr: &sqlparser.FuncExpr{
                            Qualifier: sqlparser.TableIdent{},
                            Name:      sqlparser.ColIdent{
                                _:  {
                                },
                                val:     "ISNULL",
                                lowered: "",
                                at:      0,
                            },
                            Distinct: false,
                            Exprs:    {
                                &sqlparser.AliasedExpr{
                                    Expr: &sqlparser.FuncExpr{
                                        Qualifier: sqlparser.TableIdent{},
                                        Name:      sqlparser.ColIdent{
                                            _:  {
                                            },
                                            val:     "DATEDIFF",
                                            lowered: "",
                                            at:      0,
                                        },
                                        Distinct: false,
                                        Exprs:    {
                                            !%v(DEPTH EXCEEDED),
                                            !%v(DEPTH EXCEEDED),
                                            !%v(DEPTH EXCEEDED),
                                        },
                                    },
                                    As: sqlparser.ColIdent{},
                                },
                                &sqlparser.AliasedExpr{
                                    Expr: &sqlparser.Literal{Type:1, Val:"0"},
                                    As:   sqlparser.ColIdent{},
                                },
                            },
                        },
                        As: sqlparser.ColIdent{},
                    },
                },
            },
            Right: &sqlparser.Subquery{
                Select: &sqlparser.Select{
                    Cache:            (*bool)(nil),
                    Distinct:         false,
                    StraightJoinHint: false,
                    SQLCalcFoundRows: false,
                    From:             {
                        &sqlparser.AliasedTableExpr{
                            Expr: sqlparser.TableName{
                                Name:      sqlparser.TableIdent{v:"talk"},
                                Qualifier: sqlparser.TableIdent{},
                            },
                            Partitions: nil,
                            As:         sqlparser.TableIdent{},
                            Hints:      (*sqlparser.IndexHints)(nil),
                            Columns:    nil,
                        },
                    },
                    Comments:    nil,
                    SelectExprs: {
                        &sqlparser.AliasedExpr{
                            Expr: &sqlparser.FuncExpr{
                                Qualifier: sqlparser.TableIdent{},
                                Name:      sqlparser.ColIdent{
                                    _:  {
                                    },
                                    val:     "AVG",
                                    lowered: "",
                                    at:      0,
                                },
                                Distinct: false,
                                Exprs:    {
                                    &sqlparser.AliasedExpr{
                                        Expr: &!%v(DEPTH EXCEEDED),
                                        As:   sqlparser.ColIdent{},
                                    },
                                },
                            },
                            As: sqlparser.ColIdent{},
                        },
                    },
                    Where:   (*sqlparser.Where)(nil),
                    With:    (*sqlparser.With)(nil),
                    GroupBy: nil,
                    Having:  (*sqlparser.Where)(nil),
                    OrderBy: nil,
                    Limit:   (*sqlparser.Limit)(nil),
                    Lock:    0,
                    Into:    (*sqlparser.SelectInto)(nil),
                },
            },
            Escape: nil,
        },
    },
    OrderBy: {
        &sqlparser.Order{
            Expr: &sqlparser.ColName{
                Metadata: nil,
                Name:     sqlparser.ColIdent{
                    _:  {
                    },
                    val:     "talks",
                    lowered: "",
                    at:      0,
                },
                Qualifier: sqlparser.TableName{},
            },
            Direction: 1,
        },
        &sqlparser.Order{
            Expr: &sqlparser.ColName{
                Metadata: nil,
                Name:     sqlparser.ColIdent{
                    _:  {
                    },
                    val:     "id",
                    lowered: "",
                    at:      0,
                },
                Qualifier: sqlparser.TableName{
                    Name:      sqlparser.TableIdent{v:"country"},
                    Qualifier: sqlparser.TableIdent{},
                },
            },
            Direction: 0,
        },
    },
    Limit: (*sqlparser.Limit)(nil),
    Lock:  0,
    Into:  (*sqlparser.SelectInto)(nil),
}
Code: INVALID_ARGUMENT
syntax error at position 20 near 'GROUP'
```

The error:

```
Code: INVALID_ARGUMENT
syntax error at position 20 near 'GROUP'
```

Looks pretty good too! But the error message is similar to
go-mysql-parser, not very nice.

### pg_query_go, bindings to PostgreSQL's parser

The pganalyze team built a [C
wrapper](https://github.com/pganalyze/libpg_query) that exposes
PostgreSQL's parser. Bindings to that library have been ported to many
major languages. You can read more about this effort in [this
excellent blog
post](https://pganalyze.com/blog/pg-query-2-0-postgres-query-parser). That
blog post shares a few of its many users including DuckDB and GitLab.

Let's try it out.

#### Setup

Create a new directory, set up go mod with `go mod init test`, and enter the following into `main.go`:

```go
package main

import (
	"fmt"

	"github.com/pganalyze/pg_query_go"
	"github.com/kr/pretty"
)

func main() {
	simple := "SELECT * FROM x"

	medium := "SELECT COUNT(1) AS count, name section FROM t GROUP BY name LIMIT 10"

	complex := `
SELECT
	country.country_name_eng,
	SUM(CASE WHEN talk.id IS NOT NULL THEN 1 ELSE 0 END) AS talks,
	AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) AS avg_difference
FROM country
LEFT JOIN city ON city.country_id = country.id
LEFT JOIN customer ON city.id = customer.city_id
LEFT JOIN talk ON talk.customer_id = customer.id
GROUP BY
	country.id,
	country.country_name_eng
HAVING AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) > (SELECT AVG(DATEDIFF(SECOND, talk.start_time, talk.end_time)) FROM talk)
ORDER BY talks DESC, country.id ASC;
`

	simplebad := "SELECT * FROM GROUP BY age"

	for _,  test := range []string{simple, medium, complex, simplebad} {
		ast, err := pg_query.Parse(test)
		if err != nil {
			fmt.Println(err)
			continue
		}

		fmt.Println(pretty.Sprint(ast))
	}
}
```

Run `go mod tidy` and `go run main.go`:

```go
pg_query.ParsetreeList{
    Statements: {
        pg_query.RawStmt{
            Stmt: pg_query.SelectStmt{
                DistinctClause: pg_query.List{},
                IntoClause:     (*pg_query.IntoClause)(nil),
                TargetList:     pg_query.List{
                    Items: {
                        pg_query.ResTarget{
                            Name:        (*string)(nil),
                            Indirection: pg_query.List{},
                            Val:         pg_query.ColumnRef{
                                Fields: pg_query.List{
                                    Items: {
                                        pg_query.A_Star{},
                                    },
                                },
                                Location: 7,
                            },
                            Location: 7,
                        },
                    },
                },
                FromClause: pg_query.List{
                    Items: {
                        pg_query.RangeVar{
                            Catalogname:    (*string)(nil),
                            Schemaname:     (*string)(nil),
                            Relname:        &"x",
                            Inh:            true,
                            Relpersistence: 0x70,
                            Alias:          (*pg_query.Alias)(nil),
                            Location:       14,
                        },
                    },
                },
                WhereClause:   nil,
                GroupClause:   pg_query.List{},
                HavingClause:  nil,
                WindowClause:  pg_query.List{},
                ValuesLists:   nil,
                SortClause:    pg_query.List{},
                LimitOffset:   nil,
                LimitCount:    nil,
                LockingClause: pg_query.List{},
                WithClause:    (*pg_query.WithClause)(nil),
                Op:            0x0,
                All:           false,
                Larg:          (*pg_query.SelectStmt)(nil),
                Rarg:          (*pg_query.SelectStmt)(nil),
            },
            StmtLocation: 0,
            StmtLen:      0,
        },
    },
}
pg_query.ParsetreeList{
    Statements: {
        pg_query.RawStmt{
            Stmt: pg_query.SelectStmt{
                DistinctClause: pg_query.List{},
                IntoClause:     (*pg_query.IntoClause)(nil),
                TargetList:     pg_query.List{
                    Items: {
                        pg_query.ResTarget{
                            Name:        &"count",
                            Indirection: pg_query.List{},
                            Val:         pg_query.FuncCall{
                                Funcname: pg_query.List{
                                    Items: {
                                        pg_query.String{Str:"count"},
                                    },
                                },
                                Args: pg_query.List{
                                    Items: {
                                        pg_query.A_Const{
                                            Val:      pg_query.Integer{Ival:1},
                                            Location: 13,
                                        },
                                    },
                                },
                                AggOrder:       pg_query.List{},
                                AggFilter:      nil,
                                AggWithinGroup: false,
                                AggStar:        false,
                                AggDistinct:    false,
                                FuncVariadic:   false,
                                Over:           (*pg_query.WindowDef)(nil),
                                Location:       7,
                            },
                            Location: 7,
                        },
                        pg_query.ResTarget{
                            Name:        &"section",
                            Indirection: pg_query.List{},
                            Val:         pg_query.ColumnRef{
                                Fields: pg_query.List{
                                    Items: {
                                        pg_query.String{Str:"name"},
                                    },
                                },
                                Location: 26,
                            },
                            Location: 26,
                        },
                    },
                },
                FromClause: pg_query.List{
                    Items: {
                        pg_query.RangeVar{
                            Catalogname:    (*string)(nil),
                            Schemaname:     (*string)(nil),
                            Relname:        &"t",
                            Inh:            true,
                            Relpersistence: 0x70,
                            Alias:          (*pg_query.Alias)(nil),
                            Location:       44,
                        },
                    },
                },
                WhereClause: nil,
                GroupClause: pg_query.List{
                    Items: {
                        pg_query.ColumnRef{
                            Fields: pg_query.List{
                                Items: {
                                    pg_query.String{Str:"name"},
                                },
                            },
                            Location: 55,
                        },
                    },
                },
                HavingClause: nil,
                WindowClause: pg_query.List{},
                ValuesLists:  nil,
                SortClause:   pg_query.List{},
                LimitOffset:  nil,
                LimitCount:   pg_query.A_Const{
                    Val:      pg_query.Integer{Ival:10},
                    Location: 66,
                },
                LockingClause: pg_query.List{},
                WithClause:    (*pg_query.WithClause)(nil),
                Op:            0x0,
                All:           false,
                Larg:          (*pg_query.SelectStmt)(nil),
                Rarg:          (*pg_query.SelectStmt)(nil),
            },
            StmtLocation: 0,
            StmtLen:      0,
        },
    },
}
pg_query.ParsetreeList{
    Statements: {
        pg_query.RawStmt{
            Stmt: pg_query.SelectStmt{
                DistinctClause: pg_query.List{},
                IntoClause:     (*pg_query.IntoClause)(nil),
                TargetList:     pg_query.List{
                    Items: {
                        pg_query.ResTarget{
                            Name:        (*string)(nil),
                            Indirection: pg_query.List{},
                            Val:         pg_query.ColumnRef{
                                Fields: pg_query.List{
                                    Items: {
                                        pg_query.String{Str:"country"},
                                        pg_query.String{Str:"country_name_eng"},
                                    },
                                },
                                Location: 10,
                            },
                            Location: 10,
                        },
                        pg_query.ResTarget{
                            Name:        &"talks",
                            Indirection: pg_query.List{},
                            Val:         pg_query.FuncCall{
                                Funcname: pg_query.List{
                                    Items: {
                                        pg_query.String{Str:"sum"},
                                    },
                                },
                                Args: pg_query.List{
                                    Items: {
                                        pg_query.CaseExpr{
                                            Xpr:        nil,
                                            Casetype:   0x0,
                                            Casecollid: 0x0,
                                            Arg:        nil,
                                            Args:       pg_query.List{
                                                Items: {
                                                    pg_query.CaseWhen{
                                                        Xpr:  nil,
                                                        Expr: pg_query.NullTest{
                                                            Xpr: nil,
                                                            Arg: pg_query.ColumnRef{
                                                                Fields: pg_query.List{
                                                                    Items: {
                                                                        pg_query.String{Str:"talk"},
                                                                        pg_query.String{Str:"id"},
                                                                    },
                                                                },
                                                                Location: 51,
                                                            },
                                                            Nulltesttype: 0x1,
                                                            Argisrow:     false,
                                                            Location:     59,
                                                        },
                                                        Result: pg_query.A_Const{
                                                            Val:      pg_query.Integer{Ival:1},
                                                            Location: 76,
                                                        },
                                                        Location: 46,
                                                    },
                                                },
                                            },
                                            Defresult: pg_query.A_Const{
                                                Val:      pg_query.Integer{},
                                                Location: 83,
                                            },
                                            Location: 41,
                                        },
                                    },
                                },
                                AggOrder:       pg_query.List{},
                                AggFilter:      nil,
                                AggWithinGroup: false,
                                AggStar:        false,
                                AggDistinct:    false,
                                FuncVariadic:   false,
                                Over:           (*pg_query.WindowDef)(nil),
                                Location:       37,
                            },
                            Location: 37,
                        },
                        pg_query.ResTarget{
                            Name:        &"avg_difference",
                            Indirection: pg_query.List{},
                            Val:         pg_query.FuncCall{
                                Funcname: pg_query.List{
                                    Items: {
                                        pg_query.String{Str:"avg"},
                                    },
                                },
                                Args: pg_query.List{
                                    Items: {
                                        pg_query.FuncCall{
                                            Funcname: pg_query.List{
                                                Items: {
                                                    pg_query.String{Str:"isnull"},
                                                },
                                            },
                                            Args: pg_query.List{
                                                Items: {
                                                    pg_query.FuncCall{
                                                        Funcname: pg_query.List{
                                                            Items: {
                                                                pg_query.String{Str:"datediff"},
                                                            },
                                                        },
                                                        Args: pg_query.List{
                                                            Items: {
                                                                pg_query.ColumnRef{
                                                                    Fields: pg_query.List{
                                                                        Items: {
                                                                            pg_query.String{Str:"second"},
                                                                        },
                                                                    },
                                                                    Location: 121,
                                                                },
                                                                pg_query.ColumnRef{
                                                                    Fields: pg_query.List{
                                                                        Items: {
                                                                            pg_query.String{Str:"talk"},
                                                                            pg_query.String{Str:"start_time"},
                                                                        },
                                                                    },
                                                                    Location: 129,
                                                                },
                                                                pg_query.ColumnRef{
                                                                    Fields: pg_query.List{
                                                                        Items: {
                                                                            pg_query.String{Str:"talk"},
                                                                            pg_query.String{Str:"end_time"},
                                                                        },
                                                                    },
                                                                    Location: 146,
                                                                },
                                                            },
                                                        },
                                                        AggOrder:       pg_query.List{},
                                                        AggFilter:      nil,
                                                        AggWithinGroup: false,
                                                        AggStar:        false,
                                                        AggDistinct:    false,
                                                        FuncVariadic:   false,
                                                        Over:           (*pg_query.WindowDef)(nil),
                                                        Location:       112,
                                                    },
                                                    pg_query.A_Const{
                                                        Val:      pg_query.Integer{},
                                                        Location: 161,
                                                    },
                                                },
                                            },
                                            AggOrder:       pg_query.List{},
                                            AggFilter:      nil,
                                            AggWithinGroup: false,
                                            AggStar:        false,
                                            AggDistinct:    false,
                                            FuncVariadic:   false,
                                            Over:           (*pg_query.WindowDef)(nil),
                                            Location:       105,
                                        },
                                    },
                                },
                                AggOrder:       pg_query.List{},
                                AggFilter:      nil,
                                AggWithinGroup: false,
                                AggStar:        false,
                                AggDistinct:    false,
                                FuncVariadic:   false,
                                Over:           (*pg_query.WindowDef)(nil),
                                Location:       101,
                            },
                            Location: 101,
                        },
                    },
                },
                FromClause: pg_query.List{
                    Items: {
                        pg_query.JoinExpr{
                            Jointype:  0x1,
                            IsNatural: false,
                            Larg:      pg_query.JoinExpr{
                                Jointype:  0x1,
                                IsNatural: false,
                                Larg:      pg_query.JoinExpr{
                                    Jointype:  0x1,
                                    IsNatural: false,
                                    Larg:      pg_query.RangeVar{
                                        Catalogname:    (*string)(nil),
                                        Schemaname:     (*string)(nil),
                                        Relname:        &"country",
                                        Inh:            true,
                                        Relpersistence: 0x70,
                                        Alias:          (*pg_query.Alias)(nil),
                                        Location:       188,
                                    },
                                    Rarg: pg_query.RangeVar{
                                        Catalogname:    (*string)(nil),
                                        Schemaname:     (*string)(nil),
                                        Relname:        &"city",
                                        Inh:            true,
                                        Relpersistence: 0x70,
                                        Alias:          (*pg_query.Alias)(nil),
                                        Location:       207,
                                    },
                                    UsingClause: pg_query.List{},
                                    Quals:       pg_query.A_Expr{
                                        Kind: 0x0,
                                        Name: pg_query.List{
                                            Items: {
                                                pg_query.String{Str:"="},
                                            },
                                        },
                                        Lexpr: pg_query.ColumnRef{
                                            Fields: pg_query.List{
                                                Items: {
                                                    pg_query.String{Str:"city"},
                                                    pg_query.String{Str:"country_id"},
                                                },
                                            },
                                            Location: 215,
                                        },
                                        Rexpr: pg_query.ColumnRef{
                                            Fields: pg_query.List{
                                                Items: {
                                                    pg_query.String{Str:"country"},
                                                    pg_query.String{Str:"id"},
                                                },
                                            },
                                            Location: 233,
                                        },
                                        Location: 231,
                                    },
                                    Alias:   (*pg_query.Alias)(nil),
                                    Rtindex: 0,
                                },
                                Rarg: pg_query.RangeVar{
                                    Catalogname:    (*string)(nil),
                                    Schemaname:     (*string)(nil),
                                    Relname:        &"customer",
                                    Inh:            true,
                                    Relpersistence: 0x70,
                                    Alias:          (*pg_query.Alias)(nil),
                                    Location:       254,
                                },
                                UsingClause: pg_query.List{},
                                Quals:       pg_query.A_Expr{
                                    Kind: 0x0,
                                    Name: pg_query.List{
                                        Items: {
                                            pg_query.String{Str:"="},
                                        },
                                    },
                                    Lexpr: pg_query.ColumnRef{
                                        Fields: pg_query.List{
                                            Items: {
                                                pg_query.String{Str:"city"},
                                                pg_query.String{Str:"id"},
                                            },
                                        },
                                        Location: 266,
                                    },
                                    Rexpr: pg_query.ColumnRef{
                                        Fields: pg_query.List{
                                            Items: {
                                                pg_query.String{Str:"customer"},
                                                pg_query.String{Str:"city_id"},
                                            },
                                        },
                                        Location: 276,
                                    },
                                    Location: 274,
                                },
                                Alias:   (*pg_query.Alias)(nil),
                                Rtindex: 0,
                            },
                            Rarg: pg_query.RangeVar{
                                Catalogname:    (*string)(nil),
                                Schemaname:     (*string)(nil),
                                Relname:        &"talk",
                                Inh:            true,
                                Relpersistence: 0x70,
                                Alias:          (*pg_query.Alias)(nil),
                                Location:       303,
                            },
                            UsingClause: pg_query.List{},
                            Quals:       pg_query.A_Expr{
                                Kind: 0x0,
                                Name: pg_query.List{
                                    Items: {
                                        pg_query.String{Str:"="},
                                    },
                                },
                                Lexpr: pg_query.ColumnRef{
                                    Fields: pg_query.List{
                                        Items: {
                                            pg_query.String{Str:"talk"},
                                            pg_query.String{Str:"customer_id"},
                                        },
                                    },
                                    Location: 311,
                                },
                                Rexpr: pg_query.ColumnRef{
                                    Fields: pg_query.List{
                                        Items: {
                                            pg_query.String{Str:"customer"},
                                            pg_query.String{Str:"id"},
                                        },
                                    },
                                    Location: 330,
                                },
                                Location: 328,
                            },
                            Alias:   (*pg_query.Alias)(nil),
                            Rtindex: 0,
                        },
                    },
                },
                WhereClause: nil,
                GroupClause: pg_query.List{
                    Items: {
                        pg_query.ColumnRef{
                            Fields: pg_query.List{
                                Items: {
                                    pg_query.String{Str:"country"},
                                    pg_query.String{Str:"id"},
                                },
                            },
                            Location: 353,
                        },
                        pg_query.ColumnRef{
                            Fields: pg_query.List{
                                Items: {
                                    pg_query.String{Str:"country"},
                                    pg_query.String{Str:"country_name_eng"},
                                },
                            },
                            Location: 366,
                        },
                    },
                },
                HavingClause: pg_query.A_Expr{
                    Kind: 0x0,
                    Name: pg_query.List{
                        Items: {
                            pg_query.String{Str:">"},
                        },
                    },
                    Lexpr: pg_query.FuncCall{
                        Funcname: pg_query.List{
                            Items: {
                                pg_query.String{Str:"avg"},
                            },
                        },
                        Args: pg_query.List{
                            Items: {
                                pg_query.FuncCall{
                                    Funcname: pg_query.List{
                                        Items: {
                                            pg_query.String{Str:"isnull"},
                                        },
                                    },
                                    Args: pg_query.List{
                                        Items: {
                                            pg_query.FuncCall{
                                                Funcname: pg_query.List{
                                                    Items: {
                                                        pg_query.String{Str:"datediff"},
                                                    },
                                                },
                                                Args: pg_query.List{
                                                    Items: {
                                                        pg_query.ColumnRef{
                                                            Fields: pg_query.List{
                                                                Items: {
                                                                    pg_query.String{Str:"second"},
                                                                },
                                                            },
                                                            Location: 418,
                                                        },
                                                        pg_query.ColumnRef{
                                                            Fields: pg_query.List{
                                                                Items: {
                                                                    pg_query.String{Str:"talk"},
                                                                    pg_query.String{Str:"start_time"},
                                                                },
                                                            },
                                                            Location: 426,
                                                        },
                                                        pg_query.ColumnRef{
                                                            Fields: pg_query.List{
                                                                Items: {
                                                                    pg_query.String{Str:"talk"},
                                                                    pg_query.String{Str:"end_time"},
                                                                },
                                                            },
                                                            Location: 443,
                                                        },
                                                    },
                                                },
                                                AggOrder:       pg_query.List{},
                                                AggFilter:      nil,
                                                AggWithinGroup: false,
                                                AggStar:        false,
                                                AggDistinct:    false,
                                                FuncVariadic:   false,
                                                Over:           (*pg_query.WindowDef)(nil),
                                                Location:       409,
                                            },
                                            pg_query.A_Const{
                                                Val:      pg_query.Integer{},
                                                Location: 458,
                                            },
                                        },
                                    },
                                    AggOrder:       pg_query.List{},
                                    AggFilter:      nil,
                                    AggWithinGroup: false,
                                    AggStar:        false,
                                    AggDistinct:    false,
                                    FuncVariadic:   false,
                                    Over:           (*pg_query.WindowDef)(nil),
                                    Location:       402,
                                },
                            },
                        },
                        AggOrder:       pg_query.List{},
                        AggFilter:      nil,
                        AggWithinGroup: false,
                        AggStar:        false,
                        AggDistinct:    false,
                        FuncVariadic:   false,
                        Over:           (*pg_query.WindowDef)(nil),
                        Location:       398,
                    },
                    Rexpr: pg_query.SubLink{
                        Xpr:         nil,
                        SubLinkType: 0x4,
                        SubLinkId:   0,
                        Testexpr:    nil,
                        OperName:    pg_query.List{},
                        Subselect:   pg_query.SelectStmt{
                            DistinctClause: pg_query.List{},
                            IntoClause:     (*pg_query.IntoClause)(nil),
                            TargetList:     pg_query.List{
                                Items: {
                                    pg_query.ResTarget{
                                        Name:        (*string)(nil),
                                        Indirection: pg_query.List{},
                                        Val:         pg_query.FuncCall{
                                            Funcname: pg_query.List{
                                                Items: {
                                                    pg_query.String{Str:"avg"},
                                                },
                                            },
                                            Args: pg_query.List{
                                                Items: {
                                                    pg_query.FuncCall{
                                                        Funcname: pg_query.List{
                                                            Items: {
                                                                pg_query.String{Str:"datediff"},
                                                            },
                                                        },
                                                        Args: pg_query.List{
                                                            Items: {
                                                                pg_query.ColumnRef{
                                                                    Fields: pg_query.List{
                                                                        Items: {
                                                                            pg_query.String{Str:"second"},
                                                                        },
                                                                    },
                                                                    Location: 485,
                                                                },
                                                                pg_query.ColumnRef{
                                                                    Fields: pg_query.List{
                                                                        Items: {
                                                                            pg_query.String{Str:"talk"},
                                                                            pg_query.String{Str:"start_time"},
                                                                        },
                                                                    },
                                                                    Location: 493,
                                                                },
                                                                pg_query.ColumnRef{
                                                                    Fields: pg_query.List{
                                                                        Items: {
                                                                            pg_query.String{Str:"talk"},
                                                                            pg_query.String{Str:"end_time"},
                                                                        },
                                                                    },
                                                                    Location: 510,
                                                                },
                                                            },
                                                        },
                                                        AggOrder:       pg_query.List{},
                                                        AggFilter:      nil,
                                                        AggWithinGroup: false,
                                                        AggStar:        false,
                                                        AggDistinct:    false,
                                                        FuncVariadic:   false,
                                                        Over:           (*pg_query.WindowDef)(nil),
                                                        Location:       476,
                                                    },
                                                },
                                            },
                                            AggOrder:       pg_query.List{},
                                            AggFilter:      nil,
                                            AggWithinGroup: false,
                                            AggStar:        false,
                                            AggDistinct:    false,
                                            FuncVariadic:   false,
                                            Over:           (*pg_query.WindowDef)(nil),
                                            Location:       472,
                                        },
                                        Location: 472,
                                    },
                                },
                            },
                            FromClause: pg_query.List{
                                Items: {
                                    pg_query.RangeVar{
                                        Catalogname:    (*string)(nil),
                                        Schemaname:     (*string)(nil),
                                        Relname:        &"talk",
                                        Inh:            true,
                                        Relpersistence: 0x70,
                                        Alias:          (*pg_query.Alias)(nil),
                                        Location:       531,
                                    },
                                },
                            },
                            WhereClause:   nil,
                            GroupClause:   pg_query.List{},
                            HavingClause:  nil,
                            WindowClause:  pg_query.List{},
                            ValuesLists:   nil,
                            SortClause:    pg_query.List{},
                            LimitOffset:   nil,
                            LimitCount:    nil,
                            LockingClause: pg_query.List{},
                            WithClause:    (*pg_query.WithClause)(nil),
                            Op:            0x0,
                            All:           false,
                            Larg:          (*pg_query.SelectStmt)(nil),
                            Rarg:          (*pg_query.SelectStmt)(nil),
                        },
                        Location: 464,
                    },
                    Location: 462,
                },
                WindowClause: pg_query.List{},
                ValuesLists:  nil,
                SortClause:   pg_query.List{
                    Items: {
                        pg_query.SortBy{
                            Node: pg_query.ColumnRef{
                                Fields: pg_query.List{
                                    Items: {
                                        pg_query.String{Str:"talks"},
                                    },
                                },
                                Location: 546,
                            },
                            SortbyDir:   0x2,
                            SortbyNulls: 0x0,
                            UseOp:       pg_query.List{},
                            Location:    -1,
                        },
                        pg_query.SortBy{
                            Node: pg_query.ColumnRef{
                                Fields: pg_query.List{
                                    Items: {
                                        pg_query.String{Str:"country"},
                                        pg_query.String{Str:"id"},
                                    },
                                },
                                Location: 558,
                            },
                            SortbyDir:   0x1,
                            SortbyNulls: 0x0,
                            UseOp:       pg_query.List{},
                            Location:    -1,
                        },
                    },
                },
                LimitOffset:   nil,
                LimitCount:    nil,
                LockingClause: pg_query.List{},
                WithClause:    (*pg_query.WithClause)(nil),
                Op:            0x0,
                All:           false,
                Larg:          (*pg_query.SelectStmt)(nil),
                Rarg:          (*pg_query.SelectStmt)(nil),
            },
            StmtLocation: 0,
            StmtLen:      572,
        },
    },
}
syntax error at or near "GROUP"
```

The error:

```
syntax error at or near "GROUP"
```

Looks pretty good but oh boy, PostgreSQL, that's the worst error
so far!

### Special mention: CockroachDB

CockroachDB has a juicy-looking entrypoint
[here](https://github.com/cockroachdb/cockroach/blob/master/pkg/sql/parser/parse.go#L245). But
it's hard to tell from the license under what condition it would be ok
to use, if any.

That's it for Go libraries. Let's move on to Python.

## Python

### sqlparse

From the name of [this
project](https://github.com/andialbrecht/sqlparse) it sounded like a
tool that produces a parse tree but after trying it out it seems like
it just gives you a list of tokens and not a tree. If it does give you
a tree it seems like it requires a lot of work to actually produce
it. So I'm going to skip this project.

### pglast

The only other Python library on my list is another binding to
pg_query (and thus to PostgreSQL's parser),
[pglast](https://github.com/lelit/pglast).

#### Setup

Install it with `pip3 install pglast` and enter the following into
`main.py`:

```python3
import json

import pglast.parser

simple = "SELECT * FROM x"

medium = "SELECT COUNT(1) AS count, name section FROM t GROUP BY name LIMIT 10"

_complex = """
SELECT
	country.country_name_eng,
	SUM(CASE WHEN talk.id IS NOT NULL THEN 1 ELSE 0 END) AS talks,
	AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) AS avg_difference
FROM country
LEFT JOIN city ON city.country_id = country.id
LEFT JOIN customer ON city.id = customer.city_id
LEFT JOIN talk ON talk.customer_id = customer.id
GROUP BY
	country.id,
	country.country_name_eng
HAVING AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) > (SELECT AVG(DATEDIFF(SECOND, talk.start_time, talk.end_time)) FROM talk)
ORDER BY talks DESC, country.id ASC;
"""

simplebad = "SELECT * FROM GROUP BY age"

for test in [simple, medium, _complex, simplebad]:
    stmt_json = pglast.parser.parse_sql_json(test)
    parsed = json.loads(stmt_json)
    print(json.dumps(parsed, indent=2, sort_keys=True))
```

Now normally you'd use `pglast.parser.parse_sql` which returns Python
structures but since I want to pretty print it I used their helper
function `parse_sql_json`.

Run `python3 main.py`:

```python
{
  "stmts": [
    {
      "stmt": {
        "SelectStmt": {
          "fromClause": [
            {
              "RangeVar": {
                "inh": true,
                "location": 14,
                "relname": "x",
                "relpersistence": "p"
              }
            }
          ],
          "limitOption": "LIMIT_OPTION_DEFAULT",
          "op": "SETOP_NONE",
          "targetList": [
            {
              "ResTarget": {
                "location": 7,
                "val": {
                  "ColumnRef": {
                    "fields": [
                      {
                        "A_Star": {}
                      }
                    ],
                    "location": 7
                  }
                }
              }
            }
          ]
        }
      }
    }
  ],
  "version": 130003
}
{
  "stmts": [
    {
      "stmt": {
        "SelectStmt": {
          "fromClause": [
            {
              "RangeVar": {
                "inh": true,
                "location": 44,
                "relname": "t",
                "relpersistence": "p"
              }
            }
          ],
          "groupClause": [
            {
              "ColumnRef": {
                "fields": [
                  {
                    "String": {
                      "str": "name"
                    }
                  }
                ],
                "location": 55
              }
            }
          ],
          "limitCount": {
            "A_Const": {
              "location": 66,
              "val": {
                "Integer": {
                  "ival": 10
                }
              }
            }
          },
          "limitOption": "LIMIT_OPTION_COUNT",
          "op": "SETOP_NONE",
          "targetList": [
            {
              "ResTarget": {
                "location": 7,
                "name": "count",
                "val": {
                  "FuncCall": {
                    "args": [
                      {
                        "A_Const": {
                          "location": 13,
                          "val": {
                            "Integer": {
                              "ival": 1
                            }
                          }
                        }
                      }
                    ],
                    "funcname": [
                      {
                        "String": {
                          "str": "count"
                        }
                      }
                    ],
                    "location": 7
                  }
                }
              }
            },
            {
              "ResTarget": {
                "location": 26,
                "name": "section",
                "val": {
                  "ColumnRef": {
                    "fields": [
                      {
                        "String": {
                          "str": "name"
                        }
                      }
                    ],
                    "location": 26
                  }
                }
              }
            }
          ]
        }
      }
    }
  ],
  "version": 130003
}
{
  "stmts": [
    {
      "stmt": {
        "SelectStmt": {
          "fromClause": [
            {
              "JoinExpr": {
                "jointype": "JOIN_LEFT",
                "larg": {
                  "JoinExpr": {
                    "jointype": "JOIN_LEFT",
                    "larg": {
                      "JoinExpr": {
                        "jointype": "JOIN_LEFT",
                        "larg": {
                          "RangeVar": {
                            "inh": true,
                            "location": 188,
                            "relname": "country",
                            "relpersistence": "p"
                          }
                        },
                        "quals": {
                          "A_Expr": {
                            "kind": "AEXPR_OP",
                            "lexpr": {
                              "ColumnRef": {
                                "fields": [
                                  {
                                    "String": {
                                      "str": "city"
                                    }
                                  },
                                  {
                                    "String": {
                                      "str": "country_id"
                                    }
                                  }
                                ],
                                "location": 215
                              }
                            },
                            "location": 231,
                            "name": [
                              {
                                "String": {
                                  "str": "="
                                }
                              }
                            ],
                            "rexpr": {
                              "ColumnRef": {
                                "fields": [
                                  {
                                    "String": {
                                      "str": "country"
                                    }
                                  },
                                  {
                                    "String": {
                                      "str": "id"
                                    }
                                  }
                                ],
                                "location": 233
                              }
                            }
                          }
                        },
                        "rarg": {
                          "RangeVar": {
                            "inh": true,
                            "location": 207,
                            "relname": "city",
                            "relpersistence": "p"
                          }
                        }
                      }
                    },
                    "quals": {
                      "A_Expr": {
                        "kind": "AEXPR_OP",
                        "lexpr": {
                          "ColumnRef": {
                            "fields": [
                              {
                                "String": {
                                  "str": "city"
                                }
                              },
                              {
                                "String": {
                                  "str": "id"
                                }
                              }
                            ],
                            "location": 266
                          }
                        },
                        "location": 274,
                        "name": [
                          {
                            "String": {
                              "str": "="
                            }
                          }
                        ],
                        "rexpr": {
                          "ColumnRef": {
                            "fields": [
                              {
                                "String": {
                                  "str": "customer"
                                }
                              },
                              {
                                "String": {
                                  "str": "city_id"
                                }
                              }
                            ],
                            "location": 276
                          }
                        }
                      }
                    },
                    "rarg": {
                      "RangeVar": {
                        "inh": true,
                        "location": 254,
                        "relname": "customer",
                        "relpersistence": "p"
                      }
                    }
                  }
                },
                "quals": {
                  "A_Expr": {
                    "kind": "AEXPR_OP",
                    "lexpr": {
                      "ColumnRef": {
                        "fields": [
                          {
                            "String": {
                              "str": "talk"
                            }
                          },
                          {
                            "String": {
                              "str": "customer_id"
                            }
                          }
                        ],
                        "location": 311
                      }
                    },
                    "location": 328,
                    "name": [
                      {
                        "String": {
                          "str": "="
                        }
                      }
                    ],
                    "rexpr": {
                      "ColumnRef": {
                        "fields": [
                          {
                            "String": {
                              "str": "customer"
                            }
                          },
                          {
                            "String": {
                              "str": "id"
                            }
                          }
                        ],
                        "location": 330
                      }
                    }
                  }
                },
                "rarg": {
                  "RangeVar": {
                    "inh": true,
                    "location": 303,
                    "relname": "talk",
                    "relpersistence": "p"
                  }
                }
              }
            }
          ],
          "groupClause": [
            {
              "ColumnRef": {
                "fields": [
                  {
                    "String": {
                      "str": "country"
                    }
                  },
                  {
                    "String": {
                      "str": "id"
                    }
                  }
                ],
                "location": 353
              }
            },
            {
              "ColumnRef": {
                "fields": [
                  {
                    "String": {
                      "str": "country"
                    }
                  },
                  {
                    "String": {
                      "str": "country_name_eng"
                    }
                  }
                ],
                "location": 366
              }
            }
          ],
          "havingClause": {
            "A_Expr": {
              "kind": "AEXPR_OP",
              "lexpr": {
                "FuncCall": {
                  "args": [
                    {
                      "FuncCall": {
                        "args": [
                          {
                            "FuncCall": {
                              "args": [
                                {
                                  "ColumnRef": {
                                    "fields": [
                                      {
                                        "String": {
                                          "str": "second"
                                        }
                                      }
                                    ],
                                    "location": 418
                                  }
                                },
                                {
                                  "ColumnRef": {
                                    "fields": [
                                      {
                                        "String": {
                                          "str": "talk"
                                        }
                                      },
                                      {
                                        "String": {
                                          "str": "start_time"
                                        }
                                      }
                                    ],
                                    "location": 426
                                  }
                                },
                                {
                                  "ColumnRef": {
                                    "fields": [
                                      {
                                        "String": {
                                          "str": "talk"
                                        }
                                      },
                                      {
                                        "String": {
                                          "str": "end_time"
                                        }
                                      }
                                    ],
                                    "location": 443
                                  }
                                }
                              ],
                              "funcname": [
                                {
                                  "String": {
                                    "str": "datediff"
                                  }
                                }
                              ],
                              "location": 409
                            }
                          },
                          {
                            "A_Const": {
                              "location": 458,
                              "val": {
                                "Integer": {
                                  "ival": 0
                                }
                              }
                            }
                          }
                        ],
                        "funcname": [
                          {
                            "String": {
                              "str": "isnull"
                            }
                          }
                        ],
                        "location": 402
                      }
                    }
                  ],
                  "funcname": [
                    {
                      "String": {
                        "str": "avg"
                      }
                    }
                  ],
                  "location": 398
                }
              },
              "location": 462,
              "name": [
                {
                  "String": {
                    "str": ">"
                  }
                }
              ],
              "rexpr": {
                "SubLink": {
                  "location": 464,
                  "subLinkType": "EXPR_SUBLINK",
                  "subselect": {
                    "SelectStmt": {
                      "fromClause": [
                        {
                          "RangeVar": {
                            "inh": true,
                            "location": 531,
                            "relname": "talk",
                            "relpersistence": "p"
                          }
                        }
                      ],
                      "limitOption": "LIMIT_OPTION_DEFAULT",
                      "op": "SETOP_NONE",
                      "targetList": [
                        {
                          "ResTarget": {
                            "location": 472,
                            "val": {
                              "FuncCall": {
                                "args": [
                                  {
                                    "FuncCall": {
                                      "args": [
                                        {
                                          "ColumnRef": {
                                            "fields": [
                                              {
                                                "String": {
                                                  "str": "second"
                                                }
                                              }
                                            ],
                                            "location": 485
                                          }
                                        },
                                        {
                                          "ColumnRef": {
                                            "fields": [
                                              {
                                                "String": {
                                                  "str": "talk"
                                                }
                                              },
                                              {
                                                "String": {
                                                  "str": "start_time"
                                                }
                                              }
                                            ],
                                            "location": 493
                                          }
                                        },
                                        {
                                          "ColumnRef": {
                                            "fields": [
                                              {
                                                "String": {
                                                  "str": "talk"
                                                }
                                              },
                                              {
                                                "String": {
                                                  "str": "end_time"
                                                }
                                              }
                                            ],
                                            "location": 510
                                          }
                                        }
                                      ],
                                      "funcname": [
                                        {
                                          "String": {
                                            "str": "datediff"
                                          }
                                        }
                                      ],
                                      "location": 476
                                    }
                                  }
                                ],
                                "funcname": [
                                  {
                                    "String": {
                                      "str": "avg"
                                    }
                                  }
                                ],
                                "location": 472
                              }
                            }
                          }
                        }
                      ]
                    }
                  }
                }
              }
            }
          },
          "limitOption": "LIMIT_OPTION_DEFAULT",
          "op": "SETOP_NONE",
          "sortClause": [
            {
              "SortBy": {
                "location": -1,
                "node": {
                  "ColumnRef": {
                    "fields": [
                      {
                        "String": {
                          "str": "talks"
                        }
                      }
                    ],
                    "location": 546
                  }
                },
                "sortby_dir": "SORTBY_DESC",
                "sortby_nulls": "SORTBY_NULLS_DEFAULT"
              }
            },
            {
              "SortBy": {
                "location": -1,
                "node": {
                  "ColumnRef": {
                    "fields": [
                      {
                        "String": {
                          "str": "country"
                        }
                      },
                      {
                        "String": {
                          "str": "id"
                        }
                      }
                    ],
                    "location": 558
                  }
                },
                "sortby_dir": "SORTBY_ASC",
                "sortby_nulls": "SORTBY_NULLS_DEFAULT"
              }
            }
          ],
          "targetList": [
            {
              "ResTarget": {
                "location": 10,
                "val": {
                  "ColumnRef": {
                    "fields": [
                      {
                        "String": {
                          "str": "country"
                        }
                      },
                      {
                        "String": {
                          "str": "country_name_eng"
                        }
                      }
                    ],
                    "location": 10
                  }
                }
              }
            },
            {
              "ResTarget": {
                "location": 37,
                "name": "talks",
                "val": {
                  "FuncCall": {
                    "args": [
                      {
                        "CaseExpr": {
                          "args": [
                            {
                              "CaseWhen": {
                                "expr": {
                                  "NullTest": {
                                    "arg": {
                                      "ColumnRef": {
                                        "fields": [
                                          {
                                            "String": {
                                              "str": "talk"
                                            }
                                          },
                                          {
                                            "String": {
                                              "str": "id"
                                            }
                                          }
                                        ],
                                        "location": 51
                                      }
                                    },
                                    "location": 59,
                                    "nulltesttype": "IS_NOT_NULL"
                                  }
                                },
                                "location": 46,
                                "result": {
                                  "A_Const": {
                                    "location": 76,
                                    "val": {
                                      "Integer": {
                                        "ival": 1
                                      }
                                    }
                                  }
                                }
                              }
                            }
                          ],
                          "defresult": {
                            "A_Const": {
                              "location": 83,
                              "val": {
                                "Integer": {
                                  "ival": 0
                                }
                              }
                            }
                          },
                          "location": 41
                        }
                      }
                    ],
                    "funcname": [
                      {
                        "String": {
                          "str": "sum"
                        }
                      }
                    ],
                    "location": 37
                  }
                }
              }
            },
            {
              "ResTarget": {
                "location": 101,
                "name": "avg_difference",
                "val": {
                  "FuncCall": {
                    "args": [
                      {
                        "FuncCall": {
                          "args": [
                            {
                              "FuncCall": {
                                "args": [
                                  {
                                    "ColumnRef": {
                                      "fields": [
                                        {
                                          "String": {
                                            "str": "second"
                                          }
                                        }
                                      ],
                                      "location": 121
                                    }
                                  },
                                  {
                                    "ColumnRef": {
                                      "fields": [
                                        {
                                          "String": {
                                            "str": "talk"
                                          }
                                        },
                                        {
                                          "String": {
                                            "str": "start_time"
                                          }
                                        }
                                      ],
                                      "location": 129
                                    }
                                  },
                                  {
                                    "ColumnRef": {
                                      "fields": [
                                        {
                                          "String": {
                                            "str": "talk"
                                          }
                                        },
                                        {
                                          "String": {
                                            "str": "end_time"
                                          }
                                        }
                                      ],
                                      "location": 146
                                    }
                                  }
                                ],
                                "funcname": [
                                  {
                                    "String": {
                                      "str": "datediff"
                                    }
                                  }
                                ],
                                "location": 112
                              }
                            },
                            {
                              "A_Const": {
                                "location": 161,
                                "val": {
                                  "Integer": {
                                    "ival": 0
                                  }
                                }
                              }
                            }
                          ],
                          "funcname": [
                            {
                              "String": {
                                "str": "isnull"
                              }
                            }
                          ],
                          "location": 105
                        }
                      }
                    ],
                    "funcname": [
                      {
                        "String": {
                          "str": "avg"
                        }
                      }
                    ],
                    "location": 101
                  }
                }
              }
            }
          ]
        }
      },
      "stmt_len": 572
    }
  ],
  "version": 130003
}
Traceback (most recent call last):
  File "/home/phil/multiprocess/sql-parsers/pglast/main.py", line 28, in <module>
    stmt_json = pglast.parser.parse_sql_json(test)
  File "pglast/parser.pyx", line 297, in pglast.parser.parse_sql_json
pglast.parser.ParseError: syntax error at or near "GROUP", at index 14
```

The error:

```python
Traceback (most recent call last):
  File "/home/phil/multiprocess/sql-parsers/pglast/main.py", line 28, in <module>
    stmt_json = pglast.parser.parse_sql_json(test)
  File "pglast/parser.pyx", line 297, in pglast.parser.parse_sql_json
pglast.parser.ParseError: syntax error at or near "GROUP", at index 14
```

Ok! That looks pretty normal and the error is better than
pg_query_go's (which is surprising since they both use the same C
wrapper under the hood). But still only as good as go-mysql-server and
vitess; not great.

I also just noticed the `"version": 130003` number in there which I
suspect is the PostgreSQL version. So it is worth noting that these
bindings may be a bit behind the latest release of PostgreSQL.

That's all I've got for Python libraries. Let's move on to JavaScript.

## JavaScript

### AlaSQL

[This project](https://github.com/AlaSQL/alasql) is a pure JavaScript
implementation of a SQL database. DataStation [uses
it](https://github.com/multiprocessio/datastation/blob/main/shared/languages/sql.ts#L31)
for the in-memory SQL implementation in the demo in-memory
application. Super impressive as a project.

But it does implement a unique SQL dialect (kind of similar to
ClickHouse in that regard). Its README doesn't state that it chases a
particular SQL dialect. But [the
wiki](https://github.com/AlaSQL/alasql/wiki) says it is interested in
SQL-99 compatibility.

Its [parser is
generated](https://github.com/AlaSQL/alasql/blob/develop/src/alasqlparser.jison)
with [jison](https://github.com/zaach/jison), a JavaScript port of
Bison.

#### Setup

Create a new directory, run `yarn add alasql`, and
enter the following into `main.js`:

```javascript
const alasql = require('alasql');

const simple = "SELECT * FROM x";

const medium = "SELECT COUNT(1) AS count, name section FROM t GROUP BY name LIMIT 10";

const complex = `
SELECT
	country.country_name_eng,
	SUM(CASE WHEN talk.id IS NOT NULL THEN 1 ELSE 0 END) AS talks,
	AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) AS avg_difference
FROM country
LEFT JOIN city ON city.country_id = country.id
LEFT JOIN customer ON city.id = customer.city_id
LEFT JOIN talk ON talk.customer_id = customer.id
GROUP BY
	country.id,
	country.country_name_eng
HAVING AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) > (SELECT AVG(DATEDIFF(SECOND, talk.start_time, talk.end_time)) FROM talk)
ORDER BY talks DESC, country.id ASC;
`;

const simplebad = "SELECT * FROM GROUP BY age";

for (const test of [simple, medium, complex, simplebad]) {
  let stmt;
  try {
    stmt = alasql.parse(test);
  } catch (e) {
    console.error(e);
    continue;
  }
  console.log(JSON.stringify(stmt, null, 2));
}
```

And run `node main.js`:

```
{
  "statements": [
    {
      "columns": [
        {
          "columnid": "*"
        }
      ],
      "from": [
        {
          "tableid": "x"
        }
      ]
    }
  ]
}
SyntaxError: Parse error on line 1:
SELECT COUNT(1) AS count, name section
-------------------^
Expecting 'LITERAL', 'BRALITERAL', 'NUMBER', 'STRING', 'NSTRING', got 'COUNT'
    at Parser.parser.parseError (/home/phil/multiprocess/sql-parsers/alasql/node_modules/alasql/dist/alasql.fs.js:2220:8)
    at Parser.parse (/home/phil/multiprocess/sql-parsers/alasql/node_modules/alasql/dist/alasql.fs.js:2094:22)
    at Function.alasql.parse (/home/phil/multiprocess/sql-parsers/alasql/node_modules/alasql/dist/alasql.fs.js:4454:22)
    at Object.<anonymous> (/home/phil/multiprocess/sql-parsers/alasql/main.js:28:19)
    at Module._compile (node:internal/modules/cjs/loader:1103:14)
    at Object.Module._extensions..js (node:internal/modules/cjs/loader:1155:10)
    at Module.load (node:internal/modules/cjs/loader:981:32)
    at Function.Module._load (node:internal/modules/cjs/loader:822:12)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:77:12)
    at node:internal/main/run_main_module:17:47
{
  "statements": [
    {
      "columns": [
        {
          "columnid": "country_name_eng",
          "tableid": "country"
        },
        {
          "aggregatorid": "SUM",
          "expression": {
            "whens": [
              {
                "when": {
                  "op": "IS",
                  "left": {
                    "columnid": "id",
                    "tableid": "talk"
                  },
                  "right": {
                    "op": "NOT",
                    "right": {}
                  }
                },
                "then": {
                  "value": 1
                }
              }
            ],
            "elses": {
              "value": 0
            }
          },
          "as": "talks"
        },
        {
          "aggregatorid": "AVG",
          "expression": {
            "funcid": "ISNULL",
            "args": [
              {
                "funcid": "DATEDIFF",
                "args": [
                  {
                    "value": "SECOND"
                  },
                  {
                    "columnid": "start_time",
                    "tableid": "talk"
                  },
                  {
                    "columnid": "end_time",
                    "tableid": "talk"
                  }
                ]
              },
              {
                "value": 0
              }
            ]
          },
          "as": "avg_difference"
        }
      ],
      "from": [
        {
          "tableid": "country"
        }
      ],
      "joins": [
        {
          "joinmode": "LEFT",
          "table": {
            "tableid": "city"
          },
          "on": {
            "left": {
              "columnid": "country_id",
              "tableid": "city"
            },
            "op": "=",
            "right": {
              "columnid": "id",
              "tableid": "country"
            }
          }
        },
        {
          "joinmode": "LEFT",
          "table": {
            "tableid": "customer"
          },
          "on": {
            "left": {
              "columnid": "id",
              "tableid": "city"
            },
            "op": "=",
            "right": {
              "columnid": "city_id",
              "tableid": "customer"
            }
          }
        },
        {
          "joinmode": "LEFT",
          "table": {
            "tableid": "talk"
          },
          "on": {
            "left": {
              "columnid": "customer_id",
              "tableid": "talk"
            },
            "op": "=",
            "right": {
              "columnid": "id",
              "tableid": "customer"
            }
          }
        }
      ],
      "group": [
        {
          "columnid": "id",
          "tableid": "country"
        },
        {
          "columnid": "country_name_eng",
          "tableid": "country"
        }
      ],
      "having": {
        "left": {
          "aggregatorid": "AVG",
          "expression": {
            "funcid": "ISNULL",
            "args": [
              {
                "funcid": "DATEDIFF",
                "args": [
                  {
                    "value": "SECOND"
                  },
                  {
                    "columnid": "start_time",
                    "tableid": "talk"
                  },
                  {
                    "columnid": "end_time",
                    "tableid": "talk"
                  }
                ]
              },
              {
                "value": 0
              }
            ]
          }
        },
        "op": ">",
        "right": {
          "columns": [
            {
              "aggregatorid": "AVG",
              "expression": {
                "funcid": "DATEDIFF",
                "args": [
                  {
                    "value": "SECOND"
                  },
                  {
                    "columnid": "start_time",
                    "tableid": "talk"
                  },
                  {
                    "columnid": "end_time",
                    "tableid": "talk"
                  }
                ]
              }
            }
          ],
          "from": [
            {
              "tableid": "talk"
            }
          ],
          "queriesidx": 1
        }
      },
      "order": [
        {
          "expression": {
            "columnid": "talks"
          },
          "direction": "DESC"
        },
        {
          "expression": {
            "columnid": "id",
            "tableid": "country"
          },
          "direction": "ASC"
        }
      ],
      "queries": [
        {
          "columns": [
            {
              "aggregatorid": "AVG",
              "expression": {
                "funcid": "DATEDIFF",
                "args": [
                  {
                    "value": "SECOND"
                  },
                  {
                    "columnid": "start_time",
                    "tableid": "talk"
                  },
                  {
                    "columnid": "end_time",
                    "tableid": "talk"
                  }
                ]
              }
            }
          ],
          "from": [
            {
              "tableid": "talk"
            }
          ],
          "queriesidx": 1
        }
      ]
    }
  ]
}
SyntaxError: Parse error on line 1:
SELECT * FROM GROUP BY age
--------------^
Expecting 'LITERAL', 'BRALITERAL', 'LPAR', 'STRING', 'DOLLAR', 'AT', 'COLON', 'IF', 'QUESTION', 'INSERTED', 'REPLACE', 'DATEADD', 'DATEDIFF', 'INTERVAL', 'BRAQUESTION', 'ATLBRA', 'LCUR', got 'GROUP'
    at Parser.parser.parseError (/home/phil/multiprocess/sql-parsers/alasql/node_modules/alasql/dist/alasql.fs.js:2220:8)
    at Parser.parse (/home/phil/multiprocess/sql-parsers/alasql/node_modules/alasql/dist/alasql.fs.js:2094:22)
    at Function.alasql.parse (/home/phil/multiprocess/sql-parsers/alasql/node_modules/alasql/dist/alasql.fs.js:4454:22)
    at Object.<anonymous> (/home/phil/multiprocess/sql-parsers/alasql/main.js:28:19)
    at Module._compile (node:internal/modules/cjs/loader:1103:14)
    at Object.Module._extensions..js (node:internal/modules/cjs/loader:1155:10)
    at Module.load (node:internal/modules/cjs/loader:981:32)
    at Function.Module._load (node:internal/modules/cjs/loader:822:12)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:77:12)
    at node:internal/main/run_main_module:17:47
```

The errors:

```javascript
SyntaxError: Parse error on line 1:
SELECT COUNT(1) AS count, name section
-------------------^
Expecting 'LITERAL', 'BRALITERAL', 'NUMBER', 'STRING', 'NSTRING', got 'COUNT'
    at Parser.parser.parseError (/home/phil/multiprocess/sql-parsers/alasql/node_modules/alasql/dist/alasql.fs.js:2220:8)
    at Parser.parse (/home/phil/multiprocess/sql-parsers/alasql/node_modules/alasql/dist/alasql.fs.js:2094:22)
    at Function.alasql.parse (/home/phil/multiprocess/sql-parsers/alasql/node_modules/alasql/dist/alasql.fs.js:4454:22)
    at Object.<anonymous> (/home/phil/multiprocess/sql-parsers/alasql/main.js:28:19)
    at Module._compile (node:internal/modules/cjs/loader:1103:14)
    at Object.Module._extensions..js (node:internal/modules/cjs/loader:1155:10)
    at Module.load (node:internal/modules/cjs/loader:981:32)
    at Function.Module._load (node:internal/modules/cjs/loader:822:12)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:77:12)
    at node:internal/main/run_main_module:17:47
```

And

```javascript
SyntaxError: Parse error on line 1:
SELECT * FROM GROUP BY age
--------------^
Expecting 'LITERAL', 'BRALITERAL', 'LPAR', 'STRING', 'DOLLAR', 'AT', 'COLON', 'IF', 'QUESTION', 'INSERTED', 'REPLACE', 'DATEADD', 'DATEDIFF', 'INTERVAL', 'BRAQUESTION', 'ATLBRA', 'LCUR', got 'GROUP'
    at Parser.parser.parseError (/home/phil/multiprocess/sql-parsers/alasql/node_modules/alasql/dist/alasql.fs.js:2220:8)
    at Parser.parse (/home/phil/multiprocess/sql-parsers/alasql/node_modules/alasql/dist/alasql.fs.js:2094:22)
    at Function.alasql.parse (/home/phil/multiprocess/sql-parsers/alasql/node_modules/alasql/dist/alasql.fs.js:4454:22)
    at Object.<anonymous> (/home/phil/multiprocess/sql-parsers/alasql/main.js:28:19)
    at Module._compile (node:internal/modules/cjs/loader:1103:14)
    at Object.Module._extensions..js (node:internal/modules/cjs/loader:1155:10)
    at Module.load (node:internal/modules/cjs/loader:981:32)
    at Function.Module._load (node:internal/modules/cjs/loader:822:12)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:77:12)
    at node:internal/main/run_main_module:17:47
```

I am genuinely surprised and very impressed how well it did here
because it's not a project backed by major companies and doesn't even
seem to have sponsors.

The reason it failed the first "simple" query is because I guess it
treats `count` in `AS count` as a keyword. If I change that to `countt` (an extra
`t`) it succeeds. So that's annoying but not a massive issue, and
somewhat understandable.

Also, these errors are AWESOME. This is the kind of error quality
every parser should aim for.

One concerning bit though is that it doesn't look like tokens in the
parse tree have locations. That could make it hard for external tools
to debug themselves. But that information is clearly available
somewhere in the code so maybe it's a setting I missed. And if not it
should be easy to add.

### libpg-query-node

[This project](https://github.com/pyramation/libpg-query-node) is another
binding to pg_query.

#### Setup

Create a new directory, run `yarn add libpg-query`, and
enter the following into `main.js`:

```javascript
const parser = require('libpg-query');

const simple = "SELECT * FROM x";

const medium = "SELECT COUNT(1) AS count, name section FROM t GROUP BY name LIMIT 10";

const complex = `
SELECT
	country.country_name_eng,
	SUM(CASE WHEN talk.id IS NOT NULL THEN 1 ELSE 0 END) AS talks,
	AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) AS avg_difference
FROM country
LEFT JOIN city ON city.country_id = country.id
LEFT JOIN customer ON city.id = customer.city_id
LEFT JOIN talk ON talk.customer_id = customer.id
GROUP BY
	country.id,
	country.country_name_eng
HAVING AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) > (SELECT AVG(DATEDIFF(SECOND, talk.start_time, talk.end_time)) FROM talk)
ORDER BY talks DESC, country.id ASC;
`;

const simplebad = "SELECT * FROM GROUP BY age";

for (const test of [simple, medium, complex, simplebad]) {
  let stmt;
  try {
    stmt = parser.parseQuerySync(test);
  } catch (e) {
    console.error(e);
    continue;
  }
  console.log(JSON.stringify(stmt, null, 2));
}
```

And run `node main.js`:

```json
{
  "version": 130003,
  "stmts": [
    {
      "stmt": {
        "SelectStmt": {
          "targetList": [
            {
              "ResTarget": {
                "val": {
                  "ColumnRef": {
                    "fields": [
                      {
                        "A_Star": {}
                      }
                    ],
                    "location": 7
                  }
                },
                "location": 7
              }
            }
          ],
          "fromClause": [
            {
              "RangeVar": {
                "relname": "x",
                "inh": true,
                "relpersistence": "p",
                "location": 14
              }
            }
          ],
          "limitOption": "LIMIT_OPTION_DEFAULT",
          "op": "SETOP_NONE"
        }
      }
    }
  ]
}
{
  "version": 130003,
  "stmts": [
    {
      "stmt": {
        "SelectStmt": {
          "targetList": [
            {
              "ResTarget": {
                "name": "count",
                "val": {
                  "FuncCall": {
                    "funcname": [
                      {
                        "String": {
                          "str": "count"
                        }
                      }
                    ],
                    "args": [
                      {
                        "A_Const": {
                          "val": {
                            "Integer": {
                              "ival": 1
                            }
                          },
                          "location": 13
                        }
                      }
                    ],
                    "location": 7
                  }
                },
                "location": 7
              }
            },
            {
              "ResTarget": {
                "name": "section",
                "val": {
                  "ColumnRef": {
                    "fields": [
                      {
                        "String": {
                          "str": "name"
                        }
                      }
                    ],
                    "location": 26
                  }
                },
                "location": 26
              }
            }
          ],
          "fromClause": [
            {
              "RangeVar": {
                "relname": "t",
                "inh": true,
                "relpersistence": "p",
                "location": 44
              }
            }
          ],
          "groupClause": [
            {
              "ColumnRef": {
                "fields": [
                  {
                    "String": {
                      "str": "name"
                    }
                  }
                ],
                "location": 55
              }
            }
          ],
          "limitCount": {
            "A_Const": {
              "val": {
                "Integer": {
                  "ival": 10
                }
              },
              "location": 66
            }
          },
          "limitOption": "LIMIT_OPTION_COUNT",
          "op": "SETOP_NONE"
        }
      }
    }
  ]
}
{
  "version": 130003,
  "stmts": [
    {
      "stmt": {
        "SelectStmt": {
          "targetList": [
            {
              "ResTarget": {
                "val": {
                  "ColumnRef": {
                    "fields": [
                      {
                        "String": {
                          "str": "country"
                        }
                      },
                      {
                        "String": {
                          "str": "country_name_eng"
                        }
                      }
                    ],
                    "location": 10
                  }
                },
                "location": 10
              }
            },
            {
              "ResTarget": {
                "name": "talks",
                "val": {
                  "FuncCall": {
                    "funcname": [
                      {
                        "String": {
                          "str": "sum"
                        }
                      }
                    ],
                    "args": [
                      {
                        "CaseExpr": {
                          "args": [
                            {
                              "CaseWhen": {
                                "expr": {
                                  "NullTest": {
                                    "arg": {
                                      "ColumnRef": {
                                        "fields": [
                                          {
                                            "String": {
                                              "str": "talk"
                                            }
                                          },
                                          {
                                            "String": {
                                              "str": "id"
                                            }
                                          }
                                        ],
                                        "location": 51
                                      }
                                    },
                                    "nulltesttype": "IS_NOT_NULL",
                                    "location": 59
                                  }
                                },
                                "result": {
                                  "A_Const": {
                                    "val": {
                                      "Integer": {
                                        "ival": 1
                                      }
                                    },
                                    "location": 76
                                  }
                                },
                                "location": 46
                              }
                            }
                          ],
                          "defresult": {
                            "A_Const": {
                              "val": {
                                "Integer": {
                                  "ival": 0
                                }
                              },
                              "location": 83
                            }
                          },
                          "location": 41
                        }
                      }
                    ],
                    "location": 37
                  }
                },
                "location": 37
              }
            },
            {
              "ResTarget": {
                "name": "avg_difference",
                "val": {
                  "FuncCall": {
                    "funcname": [
                      {
                        "String": {
                          "str": "avg"
                        }
                      }
                    ],
                    "args": [
                      {
                        "FuncCall": {
                          "funcname": [
                            {
                              "String": {
                                "str": "isnull"
                              }
                            }
                          ],
                          "args": [
                            {
                              "FuncCall": {
                                "funcname": [
                                  {
                                    "String": {
                                      "str": "datediff"
                                    }
                                  }
                                ],
                                "args": [
                                  {
                                    "ColumnRef": {
                                      "fields": [
                                        {
                                          "String": {
                                            "str": "second"
                                          }
                                        }
                                      ],
                                      "location": 121
                                    }
                                  },
                                  {
                                    "ColumnRef": {
                                      "fields": [
                                        {
                                          "String": {
                                            "str": "talk"
                                          }
                                        },
                                        {
                                          "String": {
                                            "str": "start_time"
                                          }
                                        }
                                      ],
                                      "location": 129
                                    }
                                  },
                                  {
                                    "ColumnRef": {
                                      "fields": [
                                        {
                                          "String": {
                                            "str": "talk"
                                          }
                                        },
                                        {
                                          "String": {
                                            "str": "end_time"
                                          }
                                        }
                                      ],
                                      "location": 146
                                    }
                                  }
                                ],
                                "location": 112
                              }
                            },
                            {
                              "A_Const": {
                                "val": {
                                  "Integer": {
                                    "ival": 0
                                  }
                                },
                                "location": 161
                              }
                            }
                          ],
                          "location": 105
                        }
                      }
                    ],
                    "location": 101
                  }
                },
                "location": 101
              }
            }
          ],
          "fromClause": [
            {
              "JoinExpr": {
                "jointype": "JOIN_LEFT",
                "larg": {
                  "JoinExpr": {
                    "jointype": "JOIN_LEFT",
                    "larg": {
                      "JoinExpr": {
                        "jointype": "JOIN_LEFT",
                        "larg": {
                          "RangeVar": {
                            "relname": "country",
                            "inh": true,
                            "relpersistence": "p",
                            "location": 188
                          }
                        },
                        "rarg": {
                          "RangeVar": {
                            "relname": "city",
                            "inh": true,
                            "relpersistence": "p",
                            "location": 207
                          }
                        },
                        "quals": {
                          "A_Expr": {
                            "kind": "AEXPR_OP",
                            "name": [
                              {
                                "String": {
                                  "str": "="
                                }
                              }
                            ],
                            "lexpr": {
                              "ColumnRef": {
                                "fields": [
                                  {
                                    "String": {
                                      "str": "city"
                                    }
                                  },
                                  {
                                    "String": {
                                      "str": "country_id"
                                    }
                                  }
                                ],
                                "location": 215
                              }
                            },
                            "rexpr": {
                              "ColumnRef": {
                                "fields": [
                                  {
                                    "String": {
                                      "str": "country"
                                    }
                                  },
                                  {
                                    "String": {
                                      "str": "id"
                                    }
                                  }
                                ],
                                "location": 233
                              }
                            },
                            "location": 231
                          }
                        }
                      }
                    },
                    "rarg": {
                      "RangeVar": {
                        "relname": "customer",
                        "inh": true,
                        "relpersistence": "p",
                        "location": 254
                      }
                    },
                    "quals": {
                      "A_Expr": {
                        "kind": "AEXPR_OP",
                        "name": [
                          {
                            "String": {
                              "str": "="
                            }
                          }
                        ],
                        "lexpr": {
                          "ColumnRef": {
                            "fields": [
                              {
                                "String": {
                                  "str": "city"
                                }
                              },
                              {
                                "String": {
                                  "str": "id"
                                }
                              }
                            ],
                            "location": 266
                          }
                        },
                        "rexpr": {
                          "ColumnRef": {
                            "fields": [
                              {
                                "String": {
                                  "str": "customer"
                                }
                              },
                              {
                                "String": {
                                  "str": "city_id"
                                }
                              }
                            ],
                            "location": 276
                          }
                        },
                        "location": 274
                      }
                    }
                  }
                },
                "rarg": {
                  "RangeVar": {
                    "relname": "talk",
                    "inh": true,
                    "relpersistence": "p",
                    "location": 303
                  }
                },
                "quals": {
                  "A_Expr": {
                    "kind": "AEXPR_OP",
                    "name": [
                      {
                        "String": {
                          "str": "="
                        }
                      }
                    ],
                    "lexpr": {
                      "ColumnRef": {
                        "fields": [
                          {
                            "String": {
                              "str": "talk"
                            }
                          },
                          {
                            "String": {
                              "str": "customer_id"
                            }
                          }
                        ],
                        "location": 311
                      }
                    },
                    "rexpr": {
                      "ColumnRef": {
                        "fields": [
                          {
                            "String": {
                              "str": "customer"
                            }
                          },
                          {
                            "String": {
                              "str": "id"
                            }
                          }
                        ],
                        "location": 330
                      }
                    },
                    "location": 328
                  }
                }
              }
            }
          ],
          "groupClause": [
            {
              "ColumnRef": {
                "fields": [
                  {
                    "String": {
                      "str": "country"
                    }
                  },
                  {
                    "String": {
                      "str": "id"
                    }
                  }
                ],
                "location": 353
              }
            },
            {
              "ColumnRef": {
                "fields": [
                  {
                    "String": {
                      "str": "country"
                    }
                  },
                  {
                    "String": {
                      "str": "country_name_eng"
                    }
                  }
                ],
                "location": 366
              }
            }
          ],
          "havingClause": {
            "A_Expr": {
              "kind": "AEXPR_OP",
              "name": [
                {
                  "String": {
                    "str": ">"
                  }
                }
              ],
              "lexpr": {
                "FuncCall": {
                  "funcname": [
                    {
                      "String": {
                        "str": "avg"
                      }
                    }
                  ],
                  "args": [
                    {
                      "FuncCall": {
                        "funcname": [
                          {
                            "String": {
                              "str": "isnull"
                            }
                          }
                        ],
                        "args": [
                          {
                            "FuncCall": {
                              "funcname": [
                                {
                                  "String": {
                                    "str": "datediff"
                                  }
                                }
                              ],
                              "args": [
                                {
                                  "ColumnRef": {
                                    "fields": [
                                      {
                                        "String": {
                                          "str": "second"
                                        }
                                      }
                                    ],
                                    "location": 418
                                  }
                                },
                                {
                                  "ColumnRef": {
                                    "fields": [
                                      {
                                        "String": {
                                          "str": "talk"
                                        }
                                      },
                                      {
                                        "String": {
                                          "str": "start_time"
                                        }
                                      }
                                    ],
                                    "location": 426
                                  }
                                },
                                {
                                  "ColumnRef": {
                                    "fields": [
                                      {
                                        "String": {
                                          "str": "talk"
                                        }
                                      },
                                      {
                                        "String": {
                                          "str": "end_time"
                                        }
                                      }
                                    ],
                                    "location": 443
                                  }
                                }
                              ],
                              "location": 409
                            }
                          },
                          {
                            "A_Const": {
                              "val": {
                                "Integer": {
                                  "ival": 0
                                }
                              },
                              "location": 458
                            }
                          }
                        ],
                        "location": 402
                      }
                    }
                  ],
                  "location": 398
                }
              },
              "rexpr": {
                "SubLink": {
                  "subLinkType": "EXPR_SUBLINK",
                  "subselect": {
                    "SelectStmt": {
                      "targetList": [
                        {
                          "ResTarget": {
                            "val": {
                              "FuncCall": {
                                "funcname": [
                                  {
                                    "String": {
                                      "str": "avg"
                                    }
                                  }
                                ],
                                "args": [
                                  {
                                    "FuncCall": {
                                      "funcname": [
                                        {
                                          "String": {
                                            "str": "datediff"
                                          }
                                        }
                                      ],
                                      "args": [
                                        {
                                          "ColumnRef": {
                                            "fields": [
                                              {
                                                "String": {
                                                  "str": "second"
                                                }
                                              }
                                            ],
                                            "location": 485
                                          }
                                        },
                                        {
                                          "ColumnRef": {
                                            "fields": [
                                              {
                                                "String": {
                                                  "str": "talk"
                                                }
                                              },
                                              {
                                                "String": {
                                                  "str": "start_time"
                                                }
                                              }
                                            ],
                                            "location": 493
                                          }
                                        },
                                        {
                                          "ColumnRef": {
                                            "fields": [
                                              {
                                                "String": {
                                                  "str": "talk"
                                                }
                                              },
                                              {
                                                "String": {
                                                  "str": "end_time"
                                                }
                                              }
                                            ],
                                            "location": 510
                                          }
                                        }
                                      ],
                                      "location": 476
                                    }
                                  }
                                ],
                                "location": 472
                              }
                            },
                            "location": 472
                          }
                        }
                      ],
                      "fromClause": [
                        {
                          "RangeVar": {
                            "relname": "talk",
                            "inh": true,
                            "relpersistence": "p",
                            "location": 531
                          }
                        }
                      ],
                      "limitOption": "LIMIT_OPTION_DEFAULT",
                      "op": "SETOP_NONE"
                    }
                  },
                  "location": 464
                }
              },
              "location": 462
            }
          },
          "sortClause": [
            {
              "SortBy": {
                "node": {
                  "ColumnRef": {
                    "fields": [
                      {
                        "String": {
                          "str": "talks"
                        }
                      }
                    ],
                    "location": 546
                  }
                },
                "sortby_dir": "SORTBY_DESC",
                "sortby_nulls": "SORTBY_NULLS_DEFAULT",
                "location": -1
              }
            },
            {
              "SortBy": {
                "node": {
                  "ColumnRef": {
                    "fields": [
                      {
                        "String": {
                          "str": "country"
                        }
                      },
                      {
                        "String": {
                          "str": "id"
                        }
                      }
                    ],
                    "location": 558
                  }
                },
                "sortby_dir": "SORTBY_ASC",
                "sortby_nulls": "SORTBY_NULLS_DEFAULT",
                "location": -1
              }
            }
          ],
          "limitOption": "LIMIT_OPTION_DEFAULT",
          "op": "SETOP_NONE"
        }
      },
      "stmt_len": 572
    }
  ]
}
Error: syntax error at or near "GROUP"
    at Object.parseQuerySync (/home/phil/multiprocess/sql-parsers/libpg-query-node/node_modules/libpg-query/index.js:21:31)
    at Object.<anonymous> (/home/phil/multiprocess/sql-parsers/libpg-query-node/main.js:28:19)
    at Module._compile (node:internal/modules/cjs/loader:1103:14)
    at Object.Module._extensions..js (node:internal/modules/cjs/loader:1155:10)
    at Module.load (node:internal/modules/cjs/loader:981:32)
    at Function.Module._load (node:internal/modules/cjs/loader:822:12)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:77:12)
    at node:internal/main/run_main_module:17:47 {
  fileName: 'scan.l',
  functionName: 'scanner_yyerror',
  lineNumber: 1234,
  cursorPosition: 15,
  context: null
}
```

Identical to the other pg_query bindings, as expected.

### Special mention: Code School's sqlite-parser

I used [this library](https://github.com/codeschool/sqlite-parser) for
a while at a previous company. It is [written with a PEG
parser](https://github.com/codeschool/sqlite-parser). Unfortunately it's no longer maintained.

That's the last JavaScript library I have. On to Rust.

## Rust

### sqlparser-rs

[This parser](https://github.com/sqlparser-rs/sqlparser-rs) is
[handwritten](https://github.com/sqlparser-rs/sqlparser-rs/blob/main/src/parser.rs). It
is used by many major projects including DataFusion and GlueSQL.

#### Setup

Create a new directory, run `cargo init`, and
enter the following into `Cargo.toml`:

```toml
[dependencies]
sqlparser = "0.16.0"
```

Since I created a `sqlparser-rs` directory my entire Cargo.toml looks like:

```toml
[package]
name = "sqlparser-rs"
version = "0.1.0"
edition = "2021"

# See more keys and their definitions at https://doc.rust-lang.org/cargo/reference/manifest.html

[dependencies]
sqlparser = "0.16.0"
```

Now put the following in `src/main.rs`:

```rust
use sqlparser::dialect::GenericDialect;
use sqlparser::parser::Parser;

fn main() {
    let simple = "SELECT * FROM x";

    let medium = "SELECT COUNT(1) AS count, name section FROM t GROUP BY name LIMIT 10";

    let complex = "
SELECT
        country.country_name_eng,
        SUM(CASE WHEN talk.id IS NOT NULL THEN 1 ELSE 0 END) AS talks,
        AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) AS avg_difference
FROM country
LEFT JOIN city ON city.country_id = country.id
LEFT JOIN customer ON city.id = customer.city_id
LEFT JOIN talk ON talk.customer_id = customer.id
GROUP BY
        country.id,
        country.country_name_eng
HAVING AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) > (SELECT AVG(DATEDIFF(SECOND, talk.start_time, talk.end_time)) FROM talk)
ORDER BY talks DESC, country.id ASC;
";

    let simplebad = "SELECT * FROM GROUP BY age";

    let tests = vec![simple, medium, complex, simplebad];

    let dialect = GenericDialect {};
    for test in tests {
        match Parser::parse_sql(&dialect, test) {
            Ok(ast) => println!("AST: {:#?}", ast),
            Err(err) => println!("Error: {:#?}", err),
        }
    }
}
```

And run `cargo run`:

```json
   Compiling sqlparser-rs v0.1.0 (/home/phil/multiprocess/sql-parsers/sqlparser-rs)
    Finished dev [unoptimized + debuginfo] target(s) in 0.31s
     Running `target/debug/sqlparser-rs`
AST: [
    Query(
        Query {
            with: None,
            body: Select(
                Select {
                    distinct: false,
                    top: None,
                    projection: [
                        Wildcard,
                    ],
                    into: None,
                    from: [
                        TableWithJoins {
                            relation: Table {
                                name: ObjectName(
                                    [
                                        Ident {
                                            value: "x",
                                            quote_style: None,
                                        },
                                    ],
                                ),
                                alias: None,
                                args: [],
                                with_hints: [],
                            },
                            joins: [],
                        },
                    ],
                    lateral_views: [],
                    selection: None,
                    group_by: [],
                    cluster_by: [],
                    distribute_by: [],
                    sort_by: [],
                    having: None,
                },
            ),
            order_by: [],
            limit: None,
            offset: None,
            fetch: None,
            lock: None,
        },
    ),
]
AST: [
    Query(
        Query {
            with: None,
            body: Select(
                Select {
                    distinct: false,
                    top: None,
                    projection: [
                        ExprWithAlias {
                            expr: Function(
                                Function {
                                    name: ObjectName(
                                        [
                                            Ident {
                                                value: "COUNT",
                                                quote_style: None,
                                            },
                                        ],
                                    ),
                                    args: [
                                        Unnamed(
                                            Expr(
                                                Value(
                                                    Number(
                                                        "1",
                                                        false,
                                                    ),
                                                ),
                                            ),
                                        ),
                                    ],
                                    over: None,
                                    distinct: false,
                                },
                            ),
                            alias: Ident {
                                value: "count",
                                quote_style: None,
                            },
                        },
                        ExprWithAlias {
                            expr: Identifier(
                                Ident {
                                    value: "name",
                                    quote_style: None,
                                },
                            ),
                            alias: Ident {
                                value: "section",
                                quote_style: None,
                            },
                        },
                    ],
                    into: None,
                    from: [
                        TableWithJoins {
                            relation: Table {
                                name: ObjectName(
                                    [
                                        Ident {
                                            value: "t",
                                            quote_style: None,
                                        },
                                    ],
                                ),
                                alias: None,
                                args: [],
                                with_hints: [],
                            },
                            joins: [],
                        },
                    ],
                    lateral_views: [],
                    selection: None,
                    group_by: [
                        Identifier(
                            Ident {
                                value: "name",
                                quote_style: None,
                            },
                        ),
                    ],
                    cluster_by: [],
                    distribute_by: [],
                    sort_by: [],
                    having: None,
                },
            ),
            order_by: [],
            limit: Some(
                Value(
                    Number(
                        "10",
                        false,
                    ),
                ),
            ),
            offset: None,
            fetch: None,
            lock: None,
        },
    ),
]
AST: [
    Query(
        Query {
            with: None,
            body: Select(
                Select {
                    distinct: false,
                    top: None,
                    projection: [
                        UnnamedExpr(
                            CompoundIdentifier(
                                [
                                    Ident {
                                        value: "country",
                                        quote_style: None,
                                    },
                                    Ident {
                                        value: "country_name_eng",
                                        quote_style: None,
                                    },
                                ],
                            ),
                        ),
                        ExprWithAlias {
                            expr: Function(
                                Function {
                                    name: ObjectName(
                                        [
                                            Ident {
                                                value: "SUM",
                                                quote_style: None,
                                            },
                                        ],
                                    ),
                                    args: [
                                        Unnamed(
                                            Expr(
                                                Case {
                                                    operand: None,
                                                    conditions: [
                                                        IsNotNull(
                                                            CompoundIdentifier(
                                                                [
                                                                    Ident {
                                                                        value: "talk",
                                                                        quote_style: None,
                                                                    },
                                                                    Ident {
                                                                        value: "id",
                                                                        quote_style: None,
                                                                    },
                                                                ],
                                                            ),
                                                        ),
                                                    ],
                                                    results: [
                                                        Value(
                                                            Number(
                                                                "1",
                                                                false,
                                                            ),
                                                        ),
                                                    ],
                                                    else_result: Some(
                                                        Value(
                                                            Number(
                                                                "0",
                                                                false,
                                                            ),
                                                        ),
                                                    ),
                                                },
                                            ),
                                        ),
                                    ],
                                    over: None,
                                    distinct: false,
                                },
                            ),
                            alias: Ident {
                                value: "talks",
                                quote_style: None,
                            },
                        },
                        ExprWithAlias {
                            expr: Function(
                                Function {
                                    name: ObjectName(
                                        [
                                            Ident {
                                                value: "AVG",
                                                quote_style: None,
                                            },
                                        ],
                                    ),
                                    args: [
                                        Unnamed(
                                            Expr(
                                                Function(
                                                    Function {
                                                        name: ObjectName(
                                                            [
                                                                Ident {
                                                                    value: "ISNULL",
                                                                    quote_style: None,
                                                                },
                                                            ],
                                                        ),
                                                        args: [
                                                            Unnamed(
                                                                Expr(
                                                                    Function(
                                                                        Function {
                                                                            name: ObjectName(
                                                                                [
                                                                                    Ident {
                                                                                        value: "DATEDIFF",
                                                                                        quote_style: None,
                                                                                    },
                                                                                ],
                                                                            ),
                                                                            args: [
                                                                                Unnamed(
                                                                                    Expr(
                                                                                        Identifier(
                                                                                            Ident {
                                                                                                value: "SECOND",
                                                                                                quote_style: None,
                                                                                            },
                                                                                        ),
                                                                                    ),
                                                                                ),
                                                                                Unnamed(
                                                                                    Expr(
                                                                                        CompoundIdentifier(
                                                                                            [
                                                                                                Ident {
                                                                                                    value: "talk",
                                                                                                    quote_style: None,
                                                                                                },
                                                                                                Ident {
                                                                                                    value: "start_time",
                                                                                                    quote_style: None,
                                                                                                },
                                                                                            ],
                                                                                        ),
                                                                                    ),
                                                                                ),
                                                                                Unnamed(
                                                                                    Expr(
                                                                                        CompoundIdentifier(
                                                                                            [
                                                                                                Ident {
                                                                                                    value: "talk",
                                                                                                    quote_style: None,
                                                                                                },
                                                                                                Ident {
                                                                                                    value: "end_time",
                                                                                                    quote_style: None,
                                                                                                },
                                                                                            ],
                                                                                        ),
                                                                                    ),
                                                                                ),
                                                                            ],
                                                                            over: None,
                                                                            distinct: false,
                                                                        },
                                                                    ),
                                                                ),
                                                            ),
                                                            Unnamed(
                                                                Expr(
                                                                    Value(
                                                                        Number(
                                                                            "0",
                                                                            false,
                                                                        ),
                                                                    ),
                                                                ),
                                                            ),
                                                        ],
                                                        over: None,
                                                        distinct: false,
                                                    },
                                                ),
                                            ),
                                        ),
                                    ],
                                    over: None,
                                    distinct: false,
                                },
                            ),
                            alias: Ident {
                                value: "avg_difference",
                                quote_style: None,
                            },
                        },
                    ],
                    into: None,
                    from: [
                        TableWithJoins {
                            relation: Table {
                                name: ObjectName(
                                    [
                                        Ident {
                                            value: "country",
                                            quote_style: None,
                                        },
                                    ],
                                ),
                                alias: None,
                                args: [],
                                with_hints: [],
                            },
                            joins: [
                                Join {
                                    relation: Table {
                                        name: ObjectName(
                                            [
                                                Ident {
                                                    value: "city",
                                                    quote_style: None,
                                                },
                                            ],
                                        ),
                                        alias: None,
                                        args: [],
                                        with_hints: [],
                                    },
                                    join_operator: LeftOuter(
                                        On(
                                            BinaryOp {
                                                left: CompoundIdentifier(
                                                    [
                                                        Ident {
                                                            value: "city",
                                                            quote_style: None,
                                                        },
                                                        Ident {
                                                            value: "country_id",
                                                            quote_style: None,
                                                        },
                                                    ],
                                                ),
                                                op: Eq,
                                                right: CompoundIdentifier(
                                                    [
                                                        Ident {
                                                            value: "country",
                                                            quote_style: None,
                                                        },
                                                        Ident {
                                                            value: "id",
                                                            quote_style: None,
                                                        },
                                                    ],
                                                ),
                                            },
                                        ),
                                    ),
                                },
                                Join {
                                    relation: Table {
                                        name: ObjectName(
                                            [
                                                Ident {
                                                    value: "customer",
                                                    quote_style: None,
                                                },
                                            ],
                                        ),
                                        alias: None,
                                        args: [],
                                        with_hints: [],
                                    },
                                    join_operator: LeftOuter(
                                        On(
                                            BinaryOp {
                                                left: CompoundIdentifier(
                                                    [
                                                        Ident {
                                                            value: "city",
                                                            quote_style: None,
                                                        },
                                                        Ident {
                                                            value: "id",
                                                            quote_style: None,
                                                        },
                                                    ],
                                                ),
                                                op: Eq,
                                                right: CompoundIdentifier(
                                                    [
                                                        Ident {
                                                            value: "customer",
                                                            quote_style: None,
                                                        },
                                                        Ident {
                                                            value: "city_id",
                                                            quote_style: None,
                                                        },
                                                    ],
                                                ),
                                            },
                                        ),
                                    ),
                                },
                                Join {
                                    relation: Table {
                                        name: ObjectName(
                                            [
                                                Ident {
                                                    value: "talk",
                                                    quote_style: None,
                                                },
                                            ],
                                        ),
                                        alias: None,
                                        args: [],
                                        with_hints: [],
                                    },
                                    join_operator: LeftOuter(
                                        On(
                                            BinaryOp {
                                                left: CompoundIdentifier(
                                                    [
                                                        Ident {
                                                            value: "talk",
                                                            quote_style: None,
                                                        },
                                                        Ident {
                                                            value: "customer_id",
                                                            quote_style: None,
                                                        },
                                                    ],
                                                ),
                                                op: Eq,
                                                right: CompoundIdentifier(
                                                    [
                                                        Ident {
                                                            value: "customer",
                                                            quote_style: None,
                                                        },
                                                        Ident {
                                                            value: "id",
                                                            quote_style: None,
                                                        },
                                                    ],
                                                ),
                                            },
                                        ),
                                    ),
                                },
                            ],
                        },
                    ],
                    lateral_views: [],
                    selection: None,
                    group_by: [
                        CompoundIdentifier(
                            [
                                Ident {
                                    value: "country",
                                    quote_style: None,
                                },
                                Ident {
                                    value: "id",
                                    quote_style: None,
                                },
                            ],
                        ),
                        CompoundIdentifier(
                            [
                                Ident {
                                    value: "country",
                                    quote_style: None,
                                },
                                Ident {
                                    value: "country_name_eng",
                                    quote_style: None,
                                },
                            ],
                        ),
                    ],
                    cluster_by: [],
                    distribute_by: [],
                    sort_by: [],
                    having: Some(
                        BinaryOp {
                            left: Function(
                                Function {
                                    name: ObjectName(
                                        [
                                            Ident {
                                                value: "AVG",
                                                quote_style: None,
                                            },
                                        ],
                                    ),
                                    args: [
                                        Unnamed(
                                            Expr(
                                                Function(
                                                    Function {
                                                        name: ObjectName(
                                                            [
                                                                Ident {
                                                                    value: "ISNULL",
                                                                    quote_style: None,
                                                                },
                                                            ],
                                                        ),
                                                        args: [
                                                            Unnamed(
                                                                Expr(
                                                                    Function(
                                                                        Function {
                                                                            name: ObjectName(
                                                                                [
                                                                                    Ident {
                                                                                        value: "DATEDIFF",
                                                                                        quote_style: None,
                                                                                    },
                                                                                ],
                                                                            ),
                                                                            args: [
                                                                                Unnamed(
                                                                                    Expr(
                                                                                        Identifier(
                                                                                            Ident {
                                                                                                value: "SECOND",
                                                                                                quote_style: None,
                                                                                            },
                                                                                        ),
                                                                                    ),
                                                                                ),
                                                                                Unnamed(
                                                                                    Expr(
                                                                                        CompoundIdentifier(
                                                                                            [
                                                                                                Ident {
                                                                                                    value: "talk",
                                                                                                    quote_style: None,
                                                                                                },
                                                                                                Ident {
                                                                                                    value: "start_time",
                                                                                                    quote_style: None,
                                                                                                },
                                                                                            ],
                                                                                        ),
                                                                                    ),
                                                                                ),
                                                                                Unnamed(
                                                                                    Expr(
                                                                                        CompoundIdentifier(
                                                                                            [
                                                                                                Ident {
                                                                                                    value: "talk",
                                                                                                    quote_style: None,
                                                                                                },
                                                                                                Ident {
                                                                                                    value: "end_time",
                                                                                                    quote_style: None,
                                                                                                },
                                                                                            ],
                                                                                        ),
                                                                                    ),
                                                                                ),
                                                                            ],
                                                                            over: None,
                                                                            distinct: false,
                                                                        },
                                                                    ),
                                                                ),
                                                            ),
                                                            Unnamed(
                                                                Expr(
                                                                    Value(
                                                                        Number(
                                                                            "0",
                                                                            false,
                                                                        ),
                                                                    ),
                                                                ),
                                                            ),
                                                        ],
                                                        over: None,
                                                        distinct: false,
                                                    },
                                                ),
                                            ),
                                        ),
                                    ],
                                    over: None,
                                    distinct: false,
                                },
                            ),
                            op: Gt,
                            right: Subquery(
                                Query {
                                    with: None,
                                    body: Select(
                                        Select {
                                            distinct: false,
                                            top: None,
                                            projection: [
                                                UnnamedExpr(
                                                    Function(
                                                        Function {
                                                            name: ObjectName(
                                                                [
                                                                    Ident {
                                                                        value: "AVG",
                                                                        quote_style: None,
                                                                    },
                                                                ],
                                                            ),
                                                            args: [
                                                                Unnamed(
                                                                    Expr(
                                                                        Function(
                                                                            Function {
                                                                                name: ObjectName(
                                                                                    [
                                                                                        Ident {
                                                                                            value: "DATEDIFF",
                                                                                            quote_style: None,
                                                                                        },
                                                                                    ],
                                                                                ),
                                                                                args: [
                                                                                    Unnamed(
                                                                                        Expr(
                                                                                            Identifier(
                                                                                                Ident {
                                                                                                    value: "SECOND",
                                                                                                    quote_style: None,
                                                                                                },
                                                                                            ),
                                                                                        ),
                                                                                    ),
                                                                                    Unnamed(
                                                                                        Expr(
                                                                                            CompoundIdentifier(
                                                                                                [
                                                                                                    Ident {
                                                                                                        value: "talk",
                                                                                                        quote_style: None,
                                                                                                    },
                                                                                                    Ident {
                                                                                                        value: "start_time",
                                                                                                        quote_style: None,
                                                                                                    },
                                                                                                ],
                                                                                            ),
                                                                                        ),
                                                                                    ),
                                                                                    Unnamed(
                                                                                        Expr(
                                                                                            CompoundIdentifier(
                                                                                                [
                                                                                                    Ident {
                                                                                                        value: "talk",
                                                                                                        quote_style: None,
                                                                                                    },
                                                                                                    Ident {
                                                                                                        value: "end_time",
                                                                                                        quote_style: None,
                                                                                                    },
                                                                                                ],
                                                                                            ),
                                                                                        ),
                                                                                    ),
                                                                                ],
                                                                                over: None,
                                                                                distinct: false,
                                                                            },
                                                                        ),
                                                                    ),
                                                                ),
                                                            ],
                                                            over: None,
                                                            distinct: false,
                                                        },
                                                    ),
                                                ),
                                            ],
                                            into: None,
                                            from: [
                                                TableWithJoins {
                                                    relation: Table {
                                                        name: ObjectName(
                                                            [
                                                                Ident {
                                                                    value: "talk",
                                                                    quote_style: None,
                                                                },
                                                            ],
                                                        ),
                                                        alias: None,
                                                        args: [],
                                                        with_hints: [],
                                                    },
                                                    joins: [],
                                                },
                                            ],
                                            lateral_views: [],
                                            selection: None,
                                            group_by: [],
                                            cluster_by: [],
                                            distribute_by: [],
                                            sort_by: [],
                                            having: None,
                                        },
                                    ),
                                    order_by: [],
                                    limit: None,
                                    offset: None,
                                    fetch: None,
                                    lock: None,
                                },
                            ),
                        },
                    ),
                },
            ),
            order_by: [
                OrderByExpr {
                    expr: Identifier(
                        Ident {
                            value: "talks",
                            quote_style: None,
                        },
                    ),
                    asc: Some(
                        false,
                    ),
                    nulls_first: None,
                },
                OrderByExpr {
                    expr: CompoundIdentifier(
                        [
                            Ident {
                                value: "country",
                                quote_style: None,
                            },
                            Ident {
                                value: "id",
                                quote_style: None,
                            },
                        ],
                    ),
                    asc: Some(
                        true,
                    ),
                    nulls_first: None,
                },
            ],
            limit: None,
            offset: None,
            fetch: None,
            lock: None,
        },
    ),
]
Error: ParserError(
    "Expected end of statement, found: age",
)
```

The error:

```
Error: ParserError(
    "Expected end of statement, found: age",
)
```

At least it knows there's an error. But that's not very useful at all
since the error happened much before `age` showed up.

And it doesn't look like location info is exported in the parsed
result. Maybe that's due to how the formatter works while printing the
struct or maybe it's really not available yet.

### pg_query.rs

Last up in Rust parsers we have another [binding to
pg_query](https://github.com/pganalyze/pg_query.rs).

#### Setup

Create a new directory, run `cargo init`, and
enter the following into `Cargo.toml`:

```toml
[dependencies]
pg_query = "0.6.0"
```

And edit `src/main.rs`:

```rust
use pg_query;

fn main() {
    let simple = "SELECT * FROM x";

    let medium = "SELECT COUNT(1) AS count, name section FROM t GROUP BY name LIMIT 10";

    let complex = "
SELECT
        country.country_name_eng,
        SUM(CASE WHEN talk.id IS NOT NULL THEN 1 ELSE 0 END) AS talks,
        AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) AS avg_difference
FROM country
LEFT JOIN city ON city.country_id = country.id
LEFT JOIN customer ON city.id = customer.city_id
LEFT JOIN talk ON talk.customer_id = customer.id
GROUP BY
        country.id,
        country.country_name_eng
HAVING AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) > (SELECT AVG(DATEDIFF(SECOND, talk.start_time, talk.end_time)) FROM talk)
ORDER BY talks DESC, country.id ASC;
";

    let simplebad = "SELECT * FROM GROUP BY age";

    let tests = vec![simple, medium, complex, simplebad];

    for test in tests {
        match pg_query::parse(test) {
            Ok(ast) => println!("AST: {:#?}", ast),
            Err(err) => println!("Error: {:#?}", err),
        }
    }
}
```

If you don't have libclang installed you'll also need that. Run `cargo run`:

```json
AST: [
    SelectStmt(
        SelectStmt {
            distinct_clause: None,
            into_clause: None,
            target_list: Some(
                [
                    ResTarget(
                        ResTarget {
                            name: None,
                            indirection: None,
                            val: Some(
                                ColumnRef(
                                    ColumnRef {
                                        fields: Some(
                                            [
                                                A_Star(
                                                    A_Star,
                                                ),
                                            ],
                                        ),
                                        location: 7,
                                    },
                                ),
                            ),
                            location: 7,
                        },
                    ),
                ],
            ),
            from_clause: Some(
                [
                    RangeVar(
                        RangeVar {
                            catalogname: None,
                            schemaname: None,
                            relname: Some(
                                "x",
                            ),
                            inh: true,
                            relpersistence: 'p',
                            alias: None,
                            location: 14,
                        },
                    ),
                ],
            ),
            where_clause: None,
            group_clause: None,
            having_clause: None,
            window_clause: None,
            values_lists: None,
            sort_clause: None,
            limit_offset: None,
            limit_count: None,
            limit_option: LIMIT_OPTION_DEFAULT,
            locking_clause: None,
            with_clause: None,
            op: SETOP_NONE,
            all: false,
            larg: None,
            rarg: None,
        },
    ),
]
AST: [
    SelectStmt(
        SelectStmt {
            distinct_clause: None,
            into_clause: None,
            target_list: Some(
                [
                    ResTarget(
                        ResTarget {
                            name: Some(
                                "count",
                            ),
                            indirection: None,
                            val: Some(
                                FuncCall(
                                    FuncCall {
                                        funcname: Some(
                                            [
                                                String {
                                                    value: Some(
                                                        "count",
                                                    ),
                                                },
                                            ],
                                        ),
                                        args: Some(
                                            [
                                                A_Const(
                                                    A_Const {
                                                        val: Value(
                                                            Integer {
                                                                value: 1,
                                                            },
                                                        ),
                                                        location: 13,
                                                    },
                                                ),
                                            ],
                                        ),
                                        agg_order: None,
                                        agg_filter: None,
                                        agg_within_group: false,
                                        agg_star: false,
                                        agg_distinct: false,
                                        func_variadic: false,
                                        over: None,
                                        location: 7,
                                    },
                                ),
                            ),
                            location: 7,
                        },
                    ),
                    ResTarget(
                        ResTarget {
                            name: Some(
                                "section",
                            ),
                            indirection: None,
                            val: Some(
                                ColumnRef(
                                    ColumnRef {
                                        fields: Some(
                                            [
                                                String {
                                                    value: Some(
                                                        "name",
                                                    ),
                                                },
                                            ],
                                        ),
                                        location: 26,
                                    },
                                ),
                            ),
                            location: 26,
                        },
                    ),
                ],
            ),
            from_clause: Some(
                [
                    RangeVar(
                        RangeVar {
                            catalogname: None,
                            schemaname: None,
                            relname: Some(
                                "t",
                            ),
                            inh: true,
                            relpersistence: 'p',
                            alias: None,
                            location: 44,
                        },
                    ),
                ],
            ),
            where_clause: None,
            group_clause: Some(
                [
                    ColumnRef(
                        ColumnRef {
                            fields: Some(
                                [
                                    String {
                                        value: Some(
                                            "name",
                                        ),
                                    },
                                ],
                            ),
                            location: 55,
                        },
                    ),
                ],
            ),
            having_clause: None,
            window_clause: None,
            values_lists: None,
            sort_clause: None,
            limit_offset: None,
            limit_count: Some(
                A_Const(
                    A_Const {
                        val: Value(
                            Integer {
                                value: 10,
                            },
                        ),
                        location: 66,
                    },
                ),
            ),
            limit_option: LIMIT_OPTION_COUNT,
            locking_clause: None,
            with_clause: None,
            op: SETOP_NONE,
            all: false,
            larg: None,
            rarg: None,
        },
    ),
]
AST: [
    SelectStmt(
        SelectStmt {
            distinct_clause: None,
            into_clause: None,
            target_list: Some(
                [
                    ResTarget(
                        ResTarget {
                            name: None,
                            indirection: None,
                            val: Some(
                                ColumnRef(
                                    ColumnRef {
                                        fields: Some(
                                            [
                                                String {
                                                    value: Some(
                                                        "country",
                                                    ),
                                                },
                                                String {
                                                    value: Some(
                                                        "country_name_eng",
                                                    ),
                                                },
                                            ],
                                        ),
                                        location: 17,
                                    },
                                ),
                            ),
                            location: 17,
                        },
                    ),
                    ResTarget(
                        ResTarget {
                            name: Some(
                                "talks",
                            ),
                            indirection: None,
                            val: Some(
                                FuncCall(
                                    FuncCall {
                                        funcname: Some(
                                            [
                                                String {
                                                    value: Some(
                                                        "sum",
                                                    ),
                                                },
                                            ],
                                        ),
                                        args: Some(
                                            [
                                                CaseExpr(
                                                    CaseExpr {
                                                        casetype: 0,
                                                        casecollid: 0,
                                                        arg: None,
                                                        args: Some(
                                                            [
                                                                CaseWhen(
                                                                    CaseWhen {
                                                                        expr: Some(
                                                                            NullTest(
                                                                                NullTest {
                                                                                    arg: Some(
                                                                                        ColumnRef(
                                                                                            ColumnRef {
                                                                                                fields: Some(
                                                                                                    [
                                                                                                        String {
                                                                                                            value: Some(
                                                                                                                "talk",
                                                                                                            ),
                                                                                                        },
                                                                                                        String {
                                                                                                            value: Some(
                                                                                                                "id",
                                                                                                            ),
                                                                                                        },
                                                                                                    ],
                                                                                                ),
                                                                                                location: 65,
                                                                                            },
                                                                                        ),
                                                                                    ),
                                                                                    nulltesttype: IS_NOT_NULL,
                                                                                    argisrow: false,
                                                                                    location: 73,
                                                                                },
                                                                            ),
                                                                        ),
                                                                        result: Some(
                                                                            A_Const(
                                                                                A_Const {
                                                                                    val: Value(
                                                                                        Integer {
                                                                                            value: 1,
                                                                                        },
                                                                                    ),
                                                                                    location: 90,
                                                                                },
                                                                            ),
                                                                        ),
                                                                        location: 60,
                                                                    },
                                                                ),
                                                            ],
                                                        ),
                                                        defresult: Some(
                                                            A_Const(
                                                                A_Const {
                                                                    val: Value(
                                                                        Integer {
                                                                            value: 0,
                                                                        },
                                                                    ),
                                                                    location: 97,
                                                                },
                                                            ),
                                                        ),
                                                        location: 55,
                                                    },
                                                ),
                                            ],
                                        ),
                                        agg_order: None,
                                        agg_filter: None,
                                        agg_within_group: false,
                                        agg_star: false,
                                        agg_distinct: false,
                                        func_variadic: false,
                                        over: None,
                                        location: 51,
                                    },
                                ),
                            ),
                            location: 51,
                        },
                    ),
                    ResTarget(
                        ResTarget {
                            name: Some(
                                "avg_difference",
                            ),
                            indirection: None,
                            val: Some(
                                FuncCall(
                                    FuncCall {
                                        funcname: Some(
                                            [
                                                String {
                                                    value: Some(
                                                        "avg",
                                                    ),
                                                },
                                            ],
                                        ),
                                        args: Some(
                                            [
                                                FuncCall(
                                                    FuncCall {
                                                        funcname: Some(
                                                            [
                                                                String {
                                                                    value: Some(
                                                                        "isnull",
                                                                    ),
                                                                },
                                                            ],
                                                        ),
                                                        args: Some(
                                                            [
                                                                FuncCall(
                                                                    FuncCall {
                                                                        funcname: Some(
                                                                            [
                                                                                String {
                                                                                    value: Some(
                                                                                        "datediff",
                                                                                    ),
                                                                                },
                                                                            ],
                                                                        ),
                                                                        args: Some(
                                                                            [
                                                                                ColumnRef(
                                                                                    ColumnRef {
                                                                                        fields: Some(
                                                                                            [
                                                                                                String {
                                                                                                    value: Some(
                                                                                                        "second",
                                                                                                    ),
                                                                                                },
                                                                                            ],
                                                                                        ),
                                                                                        location: 142,
                                                                                    },
                                                                                ),
                                                                                ColumnRef(
                                                                                    ColumnRef {
                                                                                        fields: Some(
                                                                                            [
                                                                                                String {
                                                                                                    value: Some(
                                                                                                        "talk",
                                                                                                    ),
                                                                                                },
                                                                                                String {
                                                                                                    value: Some(
                                                                                                        "start_time",
                                                                                                    ),
                                                                                                },
                                                                                            ],
                                                                                        ),
                                                                                        location: 150,
                                                                                    },
                                                                                ),
                                                                                ColumnRef(
                                                                                    ColumnRef {
                                                                                        fields: Some(
                                                                                            [
                                                                                                String {
                                                                                                    value: Some(
                                                                                                        "talk",
                                                                                                    ),
                                                                                                },
                                                                                                String {
                                                                                                    value: Some(
                                                                                                        "end_time",
                                                                                                    ),
                                                                                                },
                                                                                            ],
                                                                                        ),
                                                                                        location: 167,
                                                                                    },
                                                                                ),
                                                                            ],
                                                                        ),
                                                                        agg_order: None,
                                                                        agg_filter: None,
                                                                        agg_within_group: false,
                                                                        agg_star: false,
                                                                        agg_distinct: false,
                                                                        func_variadic: false,
                                                                        over: None,
                                                                        location: 133,
                                                                    },
                                                                ),
                                                                A_Const(
                                                                    A_Const {
                                                                        val: Value(
                                                                            Integer {
                                                                                value: 0,
                                                                            },
                                                                        ),
                                                                        location: 182,
                                                                    },
                                                                ),
                                                            ],
                                                        ),
                                                        agg_order: None,
                                                        agg_filter: None,
                                                        agg_within_group: false,
                                                        agg_star: false,
                                                        agg_distinct: false,
                                                        func_variadic: false,
                                                        over: None,
                                                        location: 126,
                                                    },
                                                ),
                                            ],
                                        ),
                                        agg_order: None,
                                        agg_filter: None,
                                        agg_within_group: false,
                                        agg_star: false,
                                        agg_distinct: false,
                                        func_variadic: false,
                                        over: None,
                                        location: 122,
                                    },
                                ),
                            ),
                            location: 122,
                        },
                    ),
                ],
            ),
            from_clause: Some(
                [
                    JoinExpr(
                        JoinExpr {
                            jointype: JOIN_LEFT,
                            is_natural: false,
                            larg: Some(
                                JoinExpr(
                                    JoinExpr {
                                        jointype: JOIN_LEFT,
                                        is_natural: false,
                                        larg: Some(
                                            JoinExpr(
                                                JoinExpr {
                                                    jointype: JOIN_LEFT,
                                                    is_natural: false,
                                                    larg: Some(
                                                        RangeVar(
                                                            RangeVar {
                                                                catalogname: None,
                                                                schemaname: None,
                                                                relname: Some(
                                                                    "country",
                                                                ),
                                                                inh: true,
                                                                relpersistence: 'p',
                                                                alias: None,
                                                                location: 209,
                                                            },
                                                        ),
                                                    ),
                                                    rarg: Some(
                                                        RangeVar(
                                                            RangeVar {
                                                                catalogname: None,
                                                                schemaname: None,
                                                                relname: Some(
                                                                    "city",
                                                                ),
                                                                inh: true,
                                                                relpersistence: 'p',
                                                                alias: None,
                                                                location: 228,
                                                            },
                                                        ),
                                                    ),
                                                    using_clause: None,
                                                    quals: Some(
                                                        A_Expr(
                                                            A_Expr {
                                                                kind: AEXPR_OP,
                                                                name: Some(
                                                                    [
                                                                        String {
                                                                            value: Some(
                                                                                "=",
                                                                            ),
                                                                        },
                                                                    ],
                                                                ),
                                                                lexpr: Some(
                                                                    ColumnRef(
                                                                        ColumnRef {
                                                                            fields: Some(
                                                                                [
                                                                                    String {
                                                                                        value: Some(
                                                                                            "city",
                                                                                        ),
                                                                                    },
                                                                                    String {
                                                                                        value: Some(
                                                                                            "country_id",
                                                                                        ),
                                                                                    },
                                                                                ],
                                                                            ),
                                                                            location: 236,
                                                                        },
                                                                    ),
                                                                ),
                                                                rexpr: Some(
                                                                    ColumnRef(
                                                                        ColumnRef {
                                                                            fields: Some(
                                                                                [
                                                                                    String {
                                                                                        value: Some(
                                                                                            "country",
                                                                                        ),
                                                                                    },
                                                                                    String {
                                                                                        value: Some(
                                                                                            "id",
                                                                                        ),
                                                                                    },
                                                                                ],
                                                                            ),
                                                                            location: 254,
                                                                        },
                                                                    ),
                                                                ),
                                                                location: 252,
                                                            },
                                                        ),
                                                    ),
                                                    alias: None,
                                                    rtindex: 0,
                                                },
                                            ),
                                        ),
                                        rarg: Some(
                                            RangeVar(
                                                RangeVar {
                                                    catalogname: None,
                                                    schemaname: None,
                                                    relname: Some(
                                                        "customer",
                                                    ),
                                                    inh: true,
                                                    relpersistence: 'p',
                                                    alias: None,
                                                    location: 275,
                                                },
                                            ),
                                        ),
                                        using_clause: None,
                                        quals: Some(
                                            A_Expr(
                                                A_Expr {
                                                    kind: AEXPR_OP,
                                                    name: Some(
                                                        [
                                                            String {
                                                                value: Some(
                                                                    "=",
                                                                ),
                                                            },
                                                        ],
                                                    ),
                                                    lexpr: Some(
                                                        ColumnRef(
                                                            ColumnRef {
                                                                fields: Some(
                                                                    [
                                                                        String {
                                                                            value: Some(
                                                                                "city",
                                                                            ),
                                                                        },
                                                                        String {
                                                                            value: Some(
                                                                                "id",
                                                                            ),
                                                                        },
                                                                    ],
                                                                ),
                                                                location: 287,
                                                            },
                                                        ),
                                                    ),
                                                    rexpr: Some(
                                                        ColumnRef(
                                                            ColumnRef {
                                                                fields: Some(
                                                                    [
                                                                        String {
                                                                            value: Some(
                                                                                "customer",
                                                                            ),
                                                                        },
                                                                        String {
                                                                            value: Some(
                                                                                "city_id",
                                                                            ),
                                                                        },
                                                                    ],
                                                                ),
                                                                location: 297,
                                                            },
                                                        ),
                                                    ),
                                                    location: 295,
                                                },
                                            ),
                                        ),
                                        alias: None,
                                        rtindex: 0,
                                    },
                                ),
                            ),
                            rarg: Some(
                                RangeVar(
                                    RangeVar {
                                        catalogname: None,
                                        schemaname: None,
                                        relname: Some(
                                            "talk",
                                        ),
                                        inh: true,
                                        relpersistence: 'p',
                                        alias: None,
                                        location: 324,
                                    },
                                ),
                            ),
                            using_clause: None,
                            quals: Some(
                                A_Expr(
                                    A_Expr {
                                        kind: AEXPR_OP,
                                        name: Some(
                                            [
                                                String {
                                                    value: Some(
                                                        "=",
                                                    ),
                                                },
                                            ],
                                        ),
                                        lexpr: Some(
                                            ColumnRef(
                                                ColumnRef {
                                                    fields: Some(
                                                        [
                                                            String {
                                                                value: Some(
                                                                    "talk",
                                                                ),
                                                            },
                                                            String {
                                                                value: Some(
                                                                    "customer_id",
                                                                ),
                                                            },
                                                        ],
                                                    ),
                                                    location: 332,
                                                },
                                            ),
                                        ),
                                        rexpr: Some(
                                            ColumnRef(
                                                ColumnRef {
                                                    fields: Some(
                                                        [
                                                            String {
                                                                value: Some(
                                                                    "customer",
                                                                ),
                                                            },
                                                            String {
                                                                value: Some(
                                                                    "id",
                                                                ),
                                                            },
                                                        ],
                                                    ),
                                                    location: 351,
                                                },
                                            ),
                                        ),
                                        location: 349,
                                    },
                                ),
                            ),
                            alias: None,
                            rtindex: 0,
                        },
                    ),
                ],
            ),
            where_clause: None,
            group_clause: Some(
                [
                    ColumnRef(
                        ColumnRef {
                            fields: Some(
                                [
                                    String {
                                        value: Some(
                                            "country",
                                        ),
                                    },
                                    String {
                                        value: Some(
                                            "id",
                                        ),
                                    },
                                ],
                            ),
                            location: 381,
                        },
                    ),
                    ColumnRef(
                        ColumnRef {
                            fields: Some(
                                [
                                    String {
                                        value: Some(
                                            "country",
                                        ),
                                    },
                                    String {
                                        value: Some(
                                            "country_name_eng",
                                        ),
                                    },
                                ],
                            ),
                            location: 401,
                        },
                    ),
                ],
            ),
            having_clause: Some(
                A_Expr(
                    A_Expr {
                        kind: AEXPR_OP,
                        name: Some(
                            [
                                String {
                                    value: Some(
                                        ">",
                                    ),
                                },
                            ],
                        ),
                        lexpr: Some(
                            FuncCall(
                                FuncCall {
                                    funcname: Some(
                                        [
                                            String {
                                                value: Some(
                                                    "avg",
                                                ),
                                            },
                                        ],
                                    ),
                                    args: Some(
                                        [
                                            FuncCall(
                                                FuncCall {
                                                    funcname: Some(
                                                        [
                                                            String {
                                                                value: Some(
                                                                    "isnull",
                                                                ),
                                                            },
                                                        ],
                                                    ),
                                                    args: Some(
                                                        [
                                                            FuncCall(
                                                                FuncCall {
                                                                    funcname: Some(
                                                                        [
                                                                            String {
                                                                                value: Some(
                                                                                    "datediff",
                                                                                ),
                                                                            },
                                                                        ],
                                                                    ),
                                                                    args: Some(
                                                                        [
                                                                            ColumnRef(
                                                                                ColumnRef {
                                                                                    fields: Some(
                                                                                        [
                                                                                            String {
                                                                                                value: Some(
                                                                                                    "second",
                                                                                                ),
                                                                                            },
                                                                                        ],
                                                                                    ),
                                                                                    location: 453,
                                                                                },
                                                                            ),
                                                                            ColumnRef(
                                                                                ColumnRef {
                                                                                    fields: Some(
                                                                                        [
                                                                                            String {
                                                                                                value: Some(
                                                                                                    "talk",
                                                                                                ),
                                                                                            },
                                                                                            String {
                                                                                                value: Some(
                                                                                                    "start_time",
                                                                                                ),
                                                                                            },
                                                                                        ],
                                                                                    ),
                                                                                    location: 461,
                                                                                },
                                                                            ),
                                                                            ColumnRef(
                                                                                ColumnRef {
                                                                                    fields: Some(
                                                                                        [
                                                                                            String {
                                                                                                value: Some(
                                                                                                    "talk",
                                                                                                ),
                                                                                            },
                                                                                            String {
                                                                                                value: Some(
                                                                                                    "end_time",
                                                                                                ),
                                                                                            },
                                                                                        ],
                                                                                    ),
                                                                                    location: 478,
                                                                                },
                                                                            ),
                                                                        ],
                                                                    ),
                                                                    agg_order: None,
                                                                    agg_filter: None,
                                                                    agg_within_group: false,
                                                                    agg_star: false,
                                                                    agg_distinct: false,
                                                                    func_variadic: false,
                                                                    over: None,
                                                                    location: 444,
                                                                },
                                                            ),
                                                            A_Const(
                                                                A_Const {
                                                                    val: Value(
                                                                        Integer {
                                                                            value: 0,
                                                                        },
                                                                    ),
                                                                    location: 493,
                                                                },
                                                            ),
                                                        ],
                                                    ),
                                                    agg_order: None,
                                                    agg_filter: None,
                                                    agg_within_group: false,
                                                    agg_star: false,
                                                    agg_distinct: false,
                                                    func_variadic: false,
                                                    over: None,
                                                    location: 437,
                                                },
                                            ),
                                        ],
                                    ),
                                    agg_order: None,
                                    agg_filter: None,
                                    agg_within_group: false,
                                    agg_star: false,
                                    agg_distinct: false,
                                    func_variadic: false,
                                    over: None,
                                    location: 433,
                                },
                            ),
                        ),
                        rexpr: Some(
                            SubLink(
                                SubLink {
                                    sub_link_type: EXPR_SUBLINK,
                                    sub_link_id: 0,
                                    testexpr: None,
                                    oper_name: None,
                                    subselect: Some(
                                        SelectStmt(
                                            SelectStmt {
                                                distinct_clause: None,
                                                into_clause: None,
                                                target_list: Some(
                                                    [
                                                        ResTarget(
                                                            ResTarget {
                                                                name: None,
                                                                indirection: None,
                                                                val: Some(
                                                                    FuncCall(
                                                                        FuncCall {
                                                                            funcname: Some(
                                                                                [
                                                                                    String {
                                                                                        value: Some(
                                                                                            "avg",
                                                                                        ),
                                                                                    },
                                                                                ],
                                                                            ),
                                                                            args: Some(
                                                                                [
                                                                                    FuncCall(
                                                                                        FuncCall {
                                                                                            funcname: Some(
                                                                                                [
                                                                                                    String {
                                                                                                        value: Some(
                                                                                                            "datediff",
                                                                                                        ),
                                                                                                    },
                                                                                                ],
                                                                                            ),
                                                                                            args: Some(
                                                                                                [
                                                                                                    ColumnRef(
                                                                                                        ColumnRef {
                                                                                                            fields: Some(
                                                                                                                [
                                                                                                                    String {
                                                                                                                        value: Some(
                                                                                                                            "second",
                                                                                                                        ),
                                                                                                                    },
                                                                                                                ],
                                                                                                            ),
                                                                                                            location: 520,
                                                                                                        },
                                                                                                    ),
                                                                                                    ColumnRef(
                                                                                                        ColumnRef {
                                                                                                            fields: Some(
                                                                                                                [
                                                                                                                    String {
                                                                                                                        value: Some(
                                                                                                                            "talk",
                                                                                                                        ),
                                                                                                                    },
                                                                                                                    String {
                                                                                                                        value: Some(
                                                                                                                            "start_time",
                                                                                                                        ),
                                                                                                                    },
                                                                                                                ],
                                                                                                            ),
                                                                                                            location: 528,
                                                                                                        },
                                                                                                    ),
                                                                                                    ColumnRef(
                                                                                                        ColumnRef {
                                                                                                            fields: Some(
                                                                                                                [
                                                                                                                    String {
                                                                                                                        value: Some(
                                                                                                                            "talk",
                                                                                                                        ),
                                                                                                                    },
                                                                                                                    String {
                                                                                                                        value: Some(
                                                                                                                            "end_time",
                                                                                                                        ),
                                                                                                                    },
                                                                                                                ],
                                                                                                            ),
                                                                                                            location: 545,
                                                                                                        },
                                                                                                    ),
                                                                                                ],
                                                                                            ),
                                                                                            agg_order: None,
                                                                                            agg_filter: None,
                                                                                            agg_within_group: false,
                                                                                            agg_star: false,
                                                                                            agg_distinct: false,
                                                                                            func_variadic: false,
                                                                                            over: None,
                                                                                            location: 511,
                                                                                        },
                                                                                    ),
                                                                                ],
                                                                            ),
                                                                            agg_order: None,
                                                                            agg_filter: None,
                                                                            agg_within_group: false,
                                                                            agg_star: false,
                                                                            agg_distinct: false,
                                                                            func_variadic: false,
                                                                            over: None,
                                                                            location: 507,
                                                                        },
                                                                    ),
                                                                ),
                                                                location: 507,
                                                            },
                                                        ),
                                                    ],
                                                ),
                                                from_clause: Some(
                                                    [
                                                        RangeVar(
                                                            RangeVar {
                                                                catalogname: None,
                                                                schemaname: None,
                                                                relname: Some(
                                                                    "talk",
                                                                ),
                                                                inh: true,
                                                                relpersistence: 'p',
                                                                alias: None,
                                                                location: 566,
                                                            },
                                                        ),
                                                    ],
                                                ),
                                                where_clause: None,
                                                group_clause: None,
                                                having_clause: None,
                                                window_clause: None,
                                                values_lists: None,
                                                sort_clause: None,
                                                limit_offset: None,
                                                limit_count: None,
                                                limit_option: LIMIT_OPTION_DEFAULT,
                                                locking_clause: None,
                                                with_clause: None,
                                                op: SETOP_NONE,
                                                all: false,
                                                larg: None,
                                                rarg: None,
                                            },
                                        ),
                                    ),
                                    location: 499,
                                },
                            ),
                        ),
                        location: 497,
                    },
                ),
            ),
            window_clause: None,
            values_lists: None,
            sort_clause: Some(
                [
                    SortBy(
                        SortBy {
                            node: Some(
                                ColumnRef(
                                    ColumnRef {
                                        fields: Some(
                                            [
                                                String {
                                                    value: Some(
                                                        "talks",
                                                    ),
                                                },
                                            ],
                                        ),
                                        location: 581,
                                    },
                                ),
                            ),
                            sortby_dir: SORTBY_DESC,
                            sortby_nulls: SORTBY_NULLS_DEFAULT,
                            use_op: None,
                            location: -1,
                        },
                    ),
                    SortBy(
                        SortBy {
                            node: Some(
                                ColumnRef(
                                    ColumnRef {
                                        fields: Some(
                                            [
                                                String {
                                                    value: Some(
                                                        "country",
                                                    ),
                                                },
                                                String {
                                                    value: Some(
                                                        "id",
                                                    ),
                                                },
                                            ],
                                        ),
                                        location: 593,
                                    },
                                ),
                            ),
                            sortby_dir: SORTBY_ASC,
                            sortby_nulls: SORTBY_NULLS_DEFAULT,
                            use_op: None,
                            location: -1,
                        },
                    ),
                ],
            ),
            limit_offset: None,
            limit_count: None,
            limit_option: LIMIT_OPTION_DEFAULT,
            locking_clause: None,
            with_clause: None,
            op: SETOP_NONE,
            all: false,
            larg: None,
            rarg: None,
        },
    ),
]
Error: ParseError(
    "syntax error at or near \"GROUP\"",
)
```

The error:

```
Error: ParseError(
    "syntax error at or near \"GROUP\"",
)
```

Identical to other pg_query bindings, as expected.

Now on to Ruby.

## Ruby

The only parser I have for Ruby is another [pg_query
binding](https://github.com/pganalyze/pg_query ). I believe this was
the first binding written by the pganalyze team.

Since all the bindings so far have been identical I don't think
there's anything meaningful to show. The docs for this binding are
good as is.

So let's move on to the final language here: Java.

## Java

### presto-parser

Presto is a SQL engine originally built at Facebook. It uses ANTLR to
generate a parser from [a
grammar](https://github.com/prestodb/presto/blob/master/presto-parser/src/main/antlr4/com/facebook/presto/sql/parser/SqlBase.g4).

#### Setup

Create a new directory and
enter the following into `pom.xml`:

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
	 xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <groupId>com.mycompany.app</groupId>
  <artifactId>my-app</artifactId>
  <version>1.0-SNAPSHOT</version>

  <properties>
    <maven.compiler.source>18</maven.compiler.source>
    <maven.compiler.target>18</maven.compiler.target>
  </properties>

  <build>
    <plugins>
      <plugin>
        <groupId>org.codehaus.mojo</groupId>
        <artifactId>exec-maven-plugin</artifactId>
        <version>1.2.1</version>
        <configuration>
          <mainClass>main.Main</mainClass>
        </configuration>
      </plugin>
    </plugins>
  </build>

  <dependencies>
    <dependency>
      <groupId>com.facebook.presto</groupId>
      <artifactId>presto-parser</artifactId>
      <version>0.272</version>
    </dependency>
    <dependency>
      <groupId>com.google.code.gson</groupId>
      <artifactId>gson</artifactId>
      <version>2.9.0</version>
    </dependency>
  </dependencies>
</project>
```

And edit `src/main/java/Main.java`:

```java
package main;

import com.facebook.presto.sql.tree.*;
import com.facebook.presto.sql.parser.*;

public class Main {
    public static void main(String[] args) {
        var simple = "SELECT * FROM x";

        var medium = "SELECT COUNT(1) AS count, name section FROM t GROUP BY name LIMIT 10";

        var complex = """
SELECT
        country.country_name_eng,
        SUM(CASE WHEN talk.id IS NOT NULL THEN 1 ELSE 0 END) AS talks,
        AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) AS avg_difference
FROM country
LEFT JOIN city ON city.country_id = country.id
LEFT JOIN customer ON city.id = customer.city_id
LEFT JOIN talk ON talk.customer_id = customer.id
GROUP BY
        country.id,
        country.country_name_eng
HAVING AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) > (SELECT AVG(DATEDIFF(SECOND, talk.start_time, talk.end_time)) FROM talk)
ORDER BY talks DESC, country.id ASC;
        """;

        var simplebad = "SELECT * FROM GROUP BY age";

        var p = new SqlParser();
        String[] tests = {simple, medium, complex, simplebad};
        for (var test : tests) {
            try {
                var query = (Query)p.createStatement(test);
                System.out.println(query);
            } catch (Exception e) {
                System.out.println(e);
            }
        }
    }
}
```

And run `mvn package` and `mvn exec:java`:

```json
Query{queryBody=QuerySpecification{select=Select{distinct=false, selectItems=[*]}, from=Optional[Table{x}], where=null, groupBy=Optional.empty, having=null, orderBy=Optional.empty, offset=null, limit=null}, orderBy=Optional.empty}
Query{queryBody=QuerySpecification{select=Select{distinct=false, selectItems=["count"(1) count, name section]}, from=Optional[Table{t}], where=null, groupBy=Optional[GroupBy{isDistinct=false, groupingElements=[SimpleGroupBy{columns=[name]}]}], having=null, orderBy=Optional.empty, offset=null, limit=10}, orderBy=Optional.empty}
com.facebook.presto.sql.parser.ParsingException: line 13:36: mismatched input ';'. Expecting: ',', 'LIMIT', 'NULLS', 'OFFSET', <EOF>
com.facebook.presto.sql.parser.ParsingException: line 1:15: mismatched input 'GROUP'. Expecting: '(', 'LATERAL', 'UNNEST', <identifier>
```

Looks like it has an issue with the semicolon at the end of the complex query. If we remove that and re-run:

```json
Query{queryBody=QuerySpecification{select=Select{distinct=false, selectItems=[*]}, from=Optional[Table{x}], where=null, groupBy=Optional.empty, having=null, orderBy=Optional.empty, offset=null, limit=null}, orderBy=Optional.empty}
Query{queryBody=QuerySpecification{select=Select{distinct=false, selectItems=["count"(1) count, name section]}, from=Optional[Table{t}], where=null, groupBy=Optional[GroupBy{isDistinct=false, groupingElements=[SimpleGroupBy{columns=[name]}]}], having=null, orderBy=Optional.empty, offset=null, limit=10}, orderBy=Optional.empty}                                                                                      Query{queryBody=QuerySpecification{select=Select{distinct=false, selectItems=[country.country_name_eng, "sum"((CASE WHEN (talk.id IS NOT NULL) THEN 1 ELSE 0 END)) talks, "avg"("isnull"("datediff"(SECOND, talk.start_time, talk.end_time), 0)) avg_difference]}, from=Optional[Join{type=LEFT, left=Join{type=LEFT, left=Join{type=LEFT, left=Table{country}, right=Table{city}, criteria=Optional[JoinOn{(city.country_id = country.id)}]}, right=Table{customer}, criteria=Optional[JoinOn{(city.id = customer.city_id)}]}, right=Table{talk}, criteria=Optional[JoinOn{(talk.customer_id = customer.id)}]}], where=null, groupBy=Optional[GroupBy{isDistinct=false, groupingElements=[SimpleGroupBy{columns=[country.id]}, SimpleGroupBy{columns=[country.country_name_eng]}]}], having=("avg"("isnull"("datediff"(SECOND, talk.start_time, talk.end_time), 0)) > (SELECT "avg"("datediff"(SECOND, talk.start_time, talk.end_time))
FROM
  talk
)), orderBy=Optional[OrderBy{sortItems=[SortItem{sortKey=talks, ordering=DESCENDING, nullOrdering=UNDEFINED}, SortItem{sortKey=country.id, ordering=ASCENDING, nullOrdering=UNDEFINED}]}], offset=null, limit=null}, orderBy=Optional.empty}
com.facebook.presto.sql.parser.ParsingException: line 1:15: mismatched input 'GROUP'. Expecting: '(', 'LATERAL', 'UNNEST', <identifier>
```

Everything succeeds/fails as expected. That error message is pretty
good too! Line number and column. Nice work, Presto developers!

### JSqlParser

The last parser for this post is
[JSqlParser](https://github.com/JSQLParser/JSqlParser). It uses
[JJTree](https://javacc.github.io/javacc/documentation/jjtree.html) to
[generate a parser from a
grammer](https://github.com/JSQLParser/JSqlParser/blob/master/src/main/jjtree/net/sf/jsqlparser/parser/JSqlParserCC.jjt).

#### Setup


Create a new directory and
enter the following into `pom.xml`:

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
	 xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  
  <groupId>com.mycompany.app</groupId>
  <artifactId>my-app</artifactId>
  <version>1.0-SNAPSHOT</version>
  
  <properties>
    <maven.compiler.source>18</maven.compiler.source>
    <maven.compiler.target>18</maven.compiler.target>
  </properties>

  <build>
    <plugins>
      <plugin>
        <groupId>org.codehaus.mojo</groupId>
        <artifactId>exec-maven-plugin</artifactId>
        <version>1.2.1</version>
        <configuration>
          <mainClass>main.Main</mainClass>
        </configuration>
      </plugin>
    </plugins>
  </build>
  
  <dependencies>
    <dependency>
      <groupId>com.github.jsqlparser</groupId>
      <artifactId>jsqlparser</artifactId>
      <version>4.2</version>
    </dependency>
  </dependencies>
</project>

```

And edit `src/main/java/Main.java`:

```java
package main;

import net.sf.jsqlparser.parser.*;


public class Main {
    public static void main(String[] args) {
        var simple = "SELECT * FROM x";
        
        var medium = "SELECT COUNT(1) AS count, name section FROM t GROUP BY name LIMIT 10";
        
        var complex = """
SELECT 
        country.country_name_eng,
        SUM(CASE WHEN talk.id IS NOT NULL THEN 1 ELSE 0 END) AS talks,
        AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) AS avg_difference
FROM country 
LEFT JOIN city ON city.country_id = country.id
LEFT JOIN customer ON city.id = customer.city_id
LEFT JOIN talk ON talk.customer_id = customer.id
GROUP BY 
        country.id,
        country.country_name_eng
HAVING AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time),0)) > (SELECT AVG(DATEDIFF(SECOND, talk.start_time, talk.end_time)) FROM talk)
ORDER BY talks DESC, country.id ASC;
        """;

        var simplebad = "SELECT * FROM GROUP BY age";

        String[] tests = {simple, medium, complex, simplebad};
        for (var test : tests) {
            try {
                var stmt = CCJSqlParserUtil.parse(test);
                System.out.println(stmt);
            } catch (Exception e) {
                System.out.println(e);
            }
        }
    }
}
```

And run `mvn package` and `mvn exec:java`:

```json
SELECT * FROM x
SELECT COUNT(1) AS count, name section FROM t GROUP BY name LIMIT 10
SELECT country.country_name_eng, SUM(CASE WHEN talk.id IS NOT NULL THEN 1 ELSE 0 END) AS talks, AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time), 0)) AS avg_difference FROM country LEFT JOIN city ON city.country_id = country.id LEFT JOIN customer ON city.id = customer.city_id LEFT JOIN talk ON talk.customer_id = customer.id GROUP BY country.id, country.country_name_eng HAVING AVG(ISNULL(DATEDIFF(SECOND, talk.start_time, talk.end_time), 0)) > (SELECT AVG(DATEDIFF(SECOND, talk.start_time, talk.end_time)) FROM talk) ORDER BY talks DESC, country.id ASC
net.sf.jsqlparser.JSQLParserException: Encountered unexpected token: "BY" "BY"
    at line 1, column 21.

Was expecting one of:

    ";"
    "ACTION"
    "ACTIVE"
    "ALGORITHM"
    "ARCHIVE"
    "ARRAY"
    "AS"
    "BYTE"
    "CASCADE"
    "CASE"
    "CAST"
    "CHANGE"
    "CHAR"
    "CHARACTER"
    "CHECKPOINT"
    "COLUMN"
    "COLUMNS"
    "COMMENT"
    "COMMIT"
    "CONNECT"
    "COSTS"
    "CYCLE"
    "DBA_RECYCLEBIN"
    "DESC"
    "DESCRIBE"
    "DISABLE"
    "DISCONNECT"
    "DIV"
    "DO"
    "DUMP"
    "DUPLICATE"
    "ENABLE"
    "END"
    "EXCLUDE"
    "EXTRACT"
    "FALSE"
    "FILTER"
    "FIRST"
    "FLUSH"
    "FN"
    "FOLLOWING"
    "FOR"
    "FORMAT"
    "GROUP"
    "HAVING"
    "HISTORY"
    "INDEX"
    "INSERT"
    "INTERVAL"
    "ISNULL"
    "JSON"
    "KEY"
    "LAST"
    "LEADING"
    "LINK"
    "LOCAL"
    "LOG"
    "MATERIALIZED"
    "NO"
    "NOLOCK"
    "NULLS"
    "OF"
    "OPEN"
    "OVER"
    "PARALLEL"
    "PARTITION"
    "PATH"
    "PERCENT"
    "PIVOT"
    "PRECISION"
    "PRIMARY"
    "PRIOR"
    "QUIESCE"
    "RANGE"
    "READ"
    "RECYCLEBIN"
    "REGISTER"
    "REPLACE"
    "RESTRICTED"
    "RESUME"
    "ROW"
    "ROWS"
    "SCHEMA"
    "SEPARATOR"
    "SEQUENCE"
    "SESSION"
    "SHUTDOWN"
    "SIBLINGS"
    "SIGNED"
    "SIZE"
    "SKIP"
    "START"
    "SUSPEND"
    "SWITCH"
    "SYNONYM"
    "TABLE"
    "TEMP"
    "TEMPORARY"
    "TIMEOUT"
    "TO"
    "TOP"
    "TRUE"
    "TRUNCATE"
    "TYPE"
    "UNQIESCE"
    "UNSIGNED"
    "USER"
    "VALIDATE"
    "VALUE"
    "VALUES"
    "VIEW"
    "WINDOW"
    "XML"
    "ZONE"
    <EOF>
    <K_DATETIMELITERAL>
    <K_DATE_LITERAL>
    <K_NEXTVAL>
    <K_STRING_FUNCTION_NAME>
    <S_CHAR_LITERAL>
    <S_IDENTIFIER>
    <S_QUOTED_IDENTIFIER>
```

Ok so this doesn't seem to have a builtin AST printer, it just prints
back the whole query as SQL, which is kind of cool but doesn't show us
the parsed structure.

The error is quite solid though. It interprets `GROUP` as a table name
which is interesting and then blows up at the unexpected "keyword"
`by`. It gives helpful line/column info too. Nice work!

## Summary

Hopefully this helps you out as you're evaluating SQL parsers for your
project!

#### Share

<blockquote class="twitter-tweet"><p lang="en" dir="ltr">Interested in SQL analysis or trying to decide between SQL parsing libraries? Here&#39;s a blog post to help you out: surveying 10+ SQL parsing libraries in Go, Ruby, Rust, Java, Python, and JavaScript.<a href="https://t.co/7Pmqh5ZNrQ">https://t.co/7Pmqh5ZNrQ</a> <a href="https://t.co/R7vIrn18sP">pic.twitter.com/R7vIrn18sP</a></p>&mdash; Multiprocess Labs (@multiprocessio) <a href="https://twitter.com/multiprocessio/status/1513925342095937541?ref_src=twsrc%5Etfw">April 12, 2022</a></blockquote> <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>

{% endblock %}
