-- The rule map as a Supabase (Postgres) table, loaded from data/rule_links.json.
-- One row per link. Ids are the chunk ids from data/rule_chunks.json.

create table if not exists rule_links (
    from_id   text not null,
    to_id     text not null,
    relation  text not null check (relation in ('overrides', 'cites', 'para_exception_of', 'shows_diagram')),
    evidence  text,
    primary key (from_id, to_id, relation)
);

-- Both directions are looked up: "what does this hit cite" and "what overrides this Law"
create index if not exists rule_links_to_id on rule_links (to_id);

-- One hop for a list of search hits ($1 is a text array of chunk ids):
-- links that start at a hit, plus alternatives and para exceptions that point at a hit.
-- When a hit is itself an alternative, run it again with the Law it overrides, to get
-- the other alternatives of that Law (retrieval/expand_with_rule_links.py does both steps)
select * from rule_links
where from_id = any($1)
   or (to_id = any($1) and relation in ('overrides', 'para_exception_of'));
