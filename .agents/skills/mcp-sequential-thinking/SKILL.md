---
name: mcp-sequential-thinking
description: A detailed tool for dynamic and reflective problem-solving through thoughts that can adapt and evolve
---

# Sequential Thinking

**If MCP server `sequential-thinking` is available**, use this tool to analyze complex problems through a flexible thinking process.

## When to Use

Use sequential-thinking when:

- Breaking down complex problems into steps
- Planning and design with room for revision
- Analysis that might need course correction
- Problems where full scope might not be clear initially
- Problems that require a multi-step solution
- Tasks that need to maintain context over multiple steps
- Situations where irrelevant information needs to be filtered out

## Key Features

- **Flexible thinking process**: You can adjust total_thoughts up or down as you progress
- **Revision support**: You can question or revise previous thoughts
- **Continuation**: You can add more thoughts even after reaching what seemed like the end
- **Uncertainty expression**: You can express uncertainty and explore alternative approaches
- **Non-linear**: Not every thought needs to build linearly - you can branch or backtrack
- **Hypothesis-driven**: Generates a solution hypothesis and verifies it

## Parameters

```python
thought: str                    # Your current thinking step
nextThoughtNeeded: bool         # True if you need more thinking, even if at what seemed like the end
thoughtNumber: int              # Current number in sequence (can go beyond initial total if needed)
totalThoughts: int             # Current estimate of thoughts needed (can be adjusted up/down)
isRevision: bool                # A boolean indicating if this thought revises previous thinking
revisesThought: int           # If is_revision is true, which thought number is being reconsidered
branchFromThought: int         # If branching, which thought number is the branching point
branchId: str                 # Identifier for the current branch (if any)
needsMoreThoughts: bool         # If reaching end but realizing more thoughts needed
```

## Workflow

1. **Start with initial estimate**: Begin with an estimate of needed thoughts, but be ready to adjust
2. **Question and revise**: Feel free to question or revise previous thoughts
3. **Don't hesitate to add thoughts**: Add more thoughts if needed, even at "end"
4. **Express uncertainty**: Express uncertainty when present
5. **Mark revisions clearly**: Mark thoughts that revise previous thinking or branch into new paths
6. **Ignore irrelevant info**: Ignore information that is irrelevant to current step
7. **Generate hypothesis**: Generate a solution hypothesis when appropriate
8. **Verify hypothesis**: Verify hypothesis based on the Chain of Thought steps
9. **Repeat until satisfied**: Repeat the process until satisfied with a solution
10. **Provide final answer**: Provide a single, ideally correct answer as final output
11. **Set nextThoughtNeeded to false**: Only when truly done and a satisfactory answer is reached

## Example Thought Progression

```
Thought 1: Analyzing the problem requirements...
Thought 2: Considering possible approaches...
Thought 3: Revising approach from Thought 2 due to X constraint...
Thought 4: Generating solution hypothesis...
Thought 5: Verifying hypothesis...
```

## Best Practices

- **Be systematic**: Follow a structured thinking process
- **Be adaptive**: Allow yourself to revise course based on new information
- **Be explicit**: Clearly mark when you're revising or branching
- **Be thorough**: Don't skip verification steps
- **Be concise**: Each thought should be focused and specific

## References

- [Sequential Thinking GitHub](https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking)
- [Model Context Protocol](https://github.com/modelcontextprotocol/servers)
