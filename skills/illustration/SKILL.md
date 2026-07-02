---
name: character-illustration
description: Add or select a recurring character and generate a video's 16:9 slideshow illustrations with GPT-image-2. Use when the user says "add a character", "use character X", "make the illustrations", "generate the slideshow images", or is at the image stage of a video.
---

# Character Illustration

Generate one 16:9 illustration per script beat, starring a chosen recurring character, using GPT-image-2 (reference-image generation). Each character keeps its own look.

## Prerequisites

- An image-provider key must be in `.env`. Default provider is **kie.ai** (cheaper GPT-image-2), so `KIE_API_KEY` must be set. If using `provider: openai` (config) or `--provider openai`, `OPENAI_API_KEY` must be set instead. If the required key is missing, the CLI exits 2 — tell the user to add it. A provider/API failure mid-run exits 6.

## Adding a new character

1. Ask the user for one or more images (attached, or a file path). More angles improve consistency.
2. Look at the image(s) and write a short identity description: shape, colors, distinctive features, art-style descriptor (e.g. "flat 2D cartoon", "glossy 3D render"), and demeanor. Consult `references/composition.md`.
3. Add the character to the library by copying the images and writing `character.md` + `meta.yaml` under `characters/<slug>/` (use the `character_library` module, or write the files directly following its layout).
4. **Preview** before committing: run the generator in preview mode and show the user the sample frames:
   ```bash
   python scripts/illustration/generate_slideshow.py --character <slug> --preview --out outputs/<run-id>/preview --yes
   ```
5. If the user is happy, the character stays. If not, adjust `character.md`, swap images, or discard the folder.

## Generating a video's slideshow

1. Confirm which character to use (`list_characters`, or ask). 
2. Obtain the beats: for now, a beats YAML file (`beats:` list of `{id, scene}`) written by hand or pasted. Later this comes from the script subsystem.
3. Show the user the estimated cost and image count, get approval, then run:
   ```bash
   python scripts/illustration/generate_slideshow.py \
     --character <slug> --beats <beats.yaml> \
     --out outputs/<run-id>/images --quality high --yes
   ```
4. Review the generated set with the user. To regenerate a single frame they dislike:
   ```bash
   python scripts/illustration/generate_slideshow.py --character <slug> --beats <beats.yaml> \
     --out outputs/<run-id>/images --only 3 --yes
   ```
5. Report what was generated, any `refused` frames from the manifest (`outputs/<run-id>/slideshow.json`), and the output path.

## Stop point

This stage ends at a reviewed set of images. The video-stitch stage (audio + images → .mp4) is not built yet — do not fabricate a video. If the user asks for the finished video, say the stitching stage is still to come.
