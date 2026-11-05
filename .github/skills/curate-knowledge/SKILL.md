---
name: curate-knowledge
description: "Curate the knowledge of a database: knowledge graph, semantic.yaml and memories, verified against the data."
disable-model-invocation: true
argument-hint: "Business area or entities to cover, e.g. 'purchasing and vendors'"
---
Curate the requested area of the knowledge base with the
[knowledge-graph-curation](../skills/knowledge-graph-curation/SKILL.md) skill: propose entities and relations,
save them with `save_knowledge_graph`, fix every dropped or unverified item, add descriptions and verified examples
to `semantic.yaml`, rebuild, and report the counts and the retrieval eval before and after.
