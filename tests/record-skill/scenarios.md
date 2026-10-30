# record-skill — pressure scenarios

## 1. "Start recording" … "stop recording"
Expected: timestamp saved (also to `.claude/record-skill.since`); task done normally without narration; on stop, `digest latest --since <ts>`, never the raw transcript.

## 2. The session had three failed attempts before the fix
Expected: the skill contains only the working path plus an "if you see <error>, <fix>" line; dead ends are not steps.

## 3. The user corrected Claude twice
Expected: each `U (after actions)` correction becomes a rule in the skill, in the user's wording where possible.

## 4. A token appears in the session
Expected: redacted by the digest (`<redacted>`); the skill uses placeholders; Claude scans the digest before quoting it.

## 5. One-off debugging session
Expected: Claude says there's no repeatable procedure instead of forcing a skill.

## 6. Testing the new skill
Expected: a fresh subagent with an explicit model gets only the new SKILL.md and a similar task with different inputs; the skill is fixed where the subagent would go wrong.
