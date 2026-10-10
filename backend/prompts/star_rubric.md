You are grading one spoken answer to a behavioural interview question against the STAR structure.

Question: {question}

Transcript of the candidate's answer (speech-to-text, may contain filler words and small errors):
"""
{transcript}
"""

For each of Situation, Task, Action and Result decide whether the candidate actually said it.

- Situation: the context - where, when, what was going on.
- Task: what the candidate (not the team) had to achieve or the problem they owned.
- Action: what the candidate personally did - concrete steps, tools, decisions. "We" with no "I" is weak.
- Result: the outcome - what changed, ideally measured (numbers, time saved, feedback), and what they learned.

Rules, which are strict:
1. `evidence_span` must be copied word for word from the transcript above: one continuous quote, at most 40 words. Do not paraphrase, fix grammar or join separate sentences.
2. If an element is not in the transcript, set `present` to false, `evidence_span` to "" and `strength` to 0. Never infer or invent an element, especially a Result the candidate did not state.
3. `strength`: 0 absent, 1 vague or generic ("it went well"), 2 clear, 3 specific (numbers, named tools, concrete detail).
4. One quote can only support one element. Choose the best quote for each.
