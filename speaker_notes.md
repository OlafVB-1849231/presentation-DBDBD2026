# Speaker notes — DBDBD 2026

## Slide 1 — Analyzing loop hoisting optimizations for recursive SQL queries

Hello everyone. My name is Olaf, and today I will talk about analyzing loop hoisting optimizations for recursive SQL queries. This is joint work with Frank Neven, Brecht Vandevoort, and Stijn Vansummeren.

<!-- The central idea is simple: recursive queries repeat a computation, but some of the work inside that computation stays the same. Can we perform that work once and reuse it across iterations? I will use a transitive closure query to explain what this means in practice. -->

## Slide 2 — Contents

I will start with the motivation for studying recursive queries, followed by a short explanation of recursion in SQL and how these queries are evaluated.

Then I will introduce loop hoisting and show where we can apply it in a query execution plan. After that, I will discuss the experiments, analyze the results, and finish with the conclusion.

## Slide 3 — Motivation

Recursion appears naturally when we work with graph data and relationships that can span an arbitrary number of steps. This has recently been a popular topic.

One example is regular path queries. These describe paths through a graph using regular expressions over edge labels. Evaluating such a query may require following paths of different lengths, rather than performing a fixed number of joins.

Another example is Datalog°, a theoretical framework that supports commutative aggregation in Datalog. It can express algorithms such as all-pairs shortest paths.

Rel, RelationalAI's language, is an example of a practical language with recursion as one of its main design principles.

These examples, as well as the previous presentation by Daan de Graaf, motivate studying recursive computations within SQL. Expressing recursion in SQL allows us to build on the efficient query planning and evaluation that many engines already provide. The opportunity lies in understanding how to execute the recursive part efficiently. That is what I will discuss in this talk.

## Slide 4 — Recursion in SQL

SQL supports recursion through recursive common table expressions, or recursive CTEs, which have been part of the SQL standard since the last century. Since the standard only allows linear, monotone recursive queries, which can all be converted to transitive closure, we focus on the execution of transitive closure, or TC.

<!-- To write a recursive CTE, we use WITH RECURSIVE, as shown on the left of the slide for transitive closure. The CTE has two terms:
- The anchor, which sets the initial state of the tc relation.
- The recursive term, which is executed repeatedly until no new tuples are found.

Note that we use UNION between these two terms, which gives us set semantics. -->

The query has two parts. The anchor query, q-a, selects the direct edges. The recursive query, q-r, extends previously discovered paths by joining their destination with the source of another edge. The UNION gives us set semantics, so repeated discoveries of the same pair do not produce additional result rows.

The algorithm on the right shows how this query is evaluated using semi-naive evaluation. Delta TC is the working table: it contains only the pairs discovered in the previous round. RT is the accumulated result table, and IT is the intermediate table for the next round.

We first evaluate the anchor query, remove duplicates, and use those rows to initialize both delta TC and RT.

In each iteration, we evaluate the recursive query using edge and the current delta TC. We deduplicate the resulting pairs and remove any pairs already in RT. The remaining pairs form IT: these are the discoveries that are actually new.

We add them to RT and use them as the next delta TC. When delta TC becomes empty, no new pairs can be found, and we return RT.

The key point is that each round extends only the newly discovered pairs. We do not extend the entire accumulated result again.

## Slide 5 — Adding loop hoisting optimizations

Repeating the same operations inside the loop creates opportunities for optimization. Let us look more closely at the highlighted line. This is the computation that produces the new pairs in each iteration. On the right, we see a possible join plan for this computation.

We join edge with delta TC to produce candidate tuples. We then deduplicate these tuples, which is commonly done using an aggregation operator. To remove results that already exist in RT, we use an anti join.

We assume that the joins are implemented using hash joins, which require building hash tables. For the join between edge and delta TC, edge is a good candidate for the build side: its hash table can be built once and reused in all subsequent iterations because the edge relation does not change.

Estimated talk time till this point: 5–6 minutes.

