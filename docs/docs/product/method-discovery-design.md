# HPLC Method Discovery & Recommendation — Product Context

## What The User Actually Wants

They do not want to search for a paper.
They do not want to extract a method for the sake of extraction.

They want to **separate specific compounds** on **their own HPLC system**, and they want to know **what worked for others on similar systems** so they can start from a proven method instead of guessing.

## Core User Input

Two things:

1. **Their system**
   - Column: manufacturer, name, chemistry, dimensions, particle size
   - Instrument constraints: available modes, detector types
   - Available mobile phases / solvents
   - Runtime preference
   - Any other practical constraints (flow rate limits, etc.)

2. **What they want to separate**
   - Target analyte(s)
   - Impurities / co-eluting risks
   - Matrix (what sample type they are working with)

## What The System Should Do

1. Accept system specs and separation target
2. Find literature that has separated the same or similar compounds on similar systems
3. Extract the final method from those papers
4. Compare extracted methods to the user’s system specs
5. Recommend the best methods ranked by how well they match the user’s system and target
6. Present the recommendation with:
   - why it fits
   - what the user needs to adjust (if anything)
   - source paper citation and evidence

## Scoring / Matching

Recommendation should score on:

- **System match**: does the literature method use a column with similar chemistry, dimensions, and particle size?
- **Analyte match**: does the paper actually separate the compound(s) I care about?
- **Matrix fit**: does the paper handle a similar sample type?
- **Practical fit**: does the method fit within the user’s instrument constraints?
- **Extraction confidence**: how well did we extract and validate the method from the paper?
- **Literature relevance**: how relevant is the paper to the user’s request overall?

The user should see **what matches, what is close, and what is a stretch** — not just a raw score.

## Current State vs Target State

- Today the CLI asks for a "request" and then scores methods vaguely
- The proper flow is: **system specs first, then target, then discovery**
- The output should say: "here is what worked for people with a system like yours"

## UX Direction

- Interactive CLI should ask for system specs first
- Then ask for separation target
- Then ask: local papers or web search?
- Then run: discover -> extract -> match -> rank -> recommend
- Output: ranked recommendations with why, evidence, citations
