# Abstracted Problem and Solution

## The Problem in Abstract Terms

Ignoring the specific domain of job search, the repository addresses a generic
information-work problem:

> A user must repeatedly inspect many noisy external streams, decide which items
> are relevant, retain institutional memory across runs, and direct scarce human
> attention only to the best new items.

This is a classic "opportunity intelligence" problem.

## The Generic Solution Pattern

The existing project implements the following reusable pattern:

1. **Source adapters**
   pull information from heterogeneous external systems.

2. **Normalization**
   transform source-specific records into a common local representation.

3. **Canonical identity**
   derive stable keys to remove duplicates and maintain memory.

4. **Rule-based prioritization**
   estimate relevance according to user-defined criteria.

5. **Persistence**
   keep the interesting subset of items across executions.

6. **Negative memory**
   remember explicitly rejected items so they do not resurface.

7. **Attention routing**
   send only the highest-value new items to interruptive channels.

8. **Review workbench**
   let the operator inspect, filter, act on, clean, and export the archive.

9. **Secondary retrieval**
   support richer exploration over the curated archive through semantics or APIs.

## Why This Pattern Is Valuable

This pattern transforms a stream into a managed corpus.

Without it, the user operates in a stateless search world:

- every session starts from zero,
- relevance must be re-evaluated repeatedly,
- deletions are not remembered,
- yesterday's work is lost,
- newness cannot be distinguished from rediscovery.

With it, the user gains cumulative leverage.

## Abstractions the Current Codebase Gets Right

### Persistence is a product feature, not a storage detail

The archive is the product's memory.
It is what makes "new" meaningful and enables durable curation.

### Thresholds are business policy

Separating save from notify is not just an implementation detail.
It encodes a correct mental model of human attention.

### Blacklist is negative training data

The blacklist is a simple but important form of user feedback.
It is a persisted statement that some discovered items should not reappear.

### Retention is archive governance

Retention prevents the archive from turning into an unbounded dumping ground.

## Where the Existing Solution Is Deliberately Simple

The project solves the pattern with a minimal, understandable stack:

- keyword rules instead of learned ranking
- SQLite instead of a service database
- one-user state instead of multi-user collaboration
- Streamlit instead of a custom application frontend
- local vector store instead of external retrieval infrastructure

This is appropriate for a personal operator tool.

## Where a Larger Product Would Generalize the Pattern

A broader, company-grade version would likely expand each stage:

- more reliable source acquisition
- richer canonicalization and entity resolution
- user profiles and preferences as first-class domain objects
- hybrid rule-based and learned ranking
- workflow history and audit trails
- collaborative review and role-specific interfaces
- experimentation and feedback loops
- more sophisticated notification policies

## Transferability Beyond Job Search

The same architecture pattern applies to:

- grant and scholarship discovery
- B2B lead sourcing
- procurement monitoring
- startup deal flow
- scientific literature watchlists
- regulatory change monitoring

In all of those domains, the hard problem is not raw retrieval.
It is selective memory, prioritization, and actionability over recurring noisy
streams.

## Final Abstraction

The current repository is a concrete instance of a broader class of systems:

> personal intelligence workbenches for recurring opportunity streams.
