# Composition & character-description guidance

## Writing a character's identity description (`character.md`)

Capture, in 1-3 sentences: overall shape/silhouette, primary colors, 2-3 distinctive features, an explicit art-style descriptor, and demeanor. The description rides in every generation prompt to reinforce the reference image.

Good: "A round orange fox mascot with an oversized blue scarf and tiny paws, flat 2D cartoon with thick outlines, perpetually cheerful."

Avoid: vague ("a cute animal") or style-free descriptions.

## Scene beats

Each beat is one clear idea. Keep the character the acting subject — doing the thing the narration describes, not standing beside a diagram. One action per frame; leave breathing room.

## Consistency tips

- Provide multiple reference angles when adding a character — it markedly improves cross-frame consistency.
- If frames drift, tighten `character.md` (add the most identity-defining features) and regenerate the drifting frames with `--only`.
