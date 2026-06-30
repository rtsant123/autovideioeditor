#!/usr/bin/env python3
"""
AUTO CLIP ENGINE  (DramaBox-style, any topic)

upload script -> Haiku breaks it into shots -> Nano Banana (via fal) makes images
-> Wan 2.2 animates each -> ordered, numbered clips zipped for a video editor.

NO stitching. You get individual clips in order to edit manually.

Stack (everything except Haiku runs through fal -> one vendor, one bill):
  - Script director : Claude Haiku           (Anthropic API)  ANTHROPIC_API_KEY
  - Images          : Nano Banana            (fal)            FAL_KEY
  - Video           : Wan 2.2 image-to-video (fal)            FAL_KEY

Standalone:
    python engine.py myscript.txt vertical
    (sizes: vertical | landscape | square)
"""

import os
import re
import sys
import json
import time
import zipfile
import pathlib

import requests

try:
    import fal_client
    from anthropic import Anthropic
except ImportError:
    print("Run:  pip install fal-client anthropic requests")
    sys.exit(1)

# ---- models (swap any of these later) ----
DIRECTOR_MODEL = "claude-haiku-4-5-20251001"
IMAGE_T2I      = "fal-ai/nano-banana"                          # text -> image
IMAGE_EDIT     = "fal-ai/nano-banana/edit"                     # image+text -> image (keeps a character)
VIDEO_MODEL    = "fal-ai/wan/v2.2-a14b/image-to-video/turbo"   # Wan 2.2 turbo

SIZES = {"vertical": "9:16", "landscape": "16:9", "square": "1:1"}
VIDEO_RES = "720p"


def log(m): print(f"  {m}", flush=True)


def on_update(update):
    if isinstance(update, fal_client.InProgress):
        for e in update.logs:
            log(e["message"])


def fal_call(model, args, tries=3):
    last = None
    for i in range(1, tries + 1):
        try:
            return fal_client.subscribe(model, arguments=args,
                                        with_logs=True, on_queue_update=on_update)
        except Exception as e:
            last = e; log(f"  retry {i}/{tries}: {e}"); time.sleep(2 * i)
    raise last


def download(url, dest):
    r = requests.get(url, timeout=600); r.raise_for_status()
    dest.write_bytes(r.content)


# ---------- STEP 1: Haiku -> shot list ----------
DIRECTOR_SYSTEM = """You are a video director. Turn the user's script into a shot list for an AI image+video pipeline.

Return ONLY valid JSON, no markdown, no commentary. Schema:
{
  "title": "short title",
  "characters": [
    {"name": "Name", "description": "fixed, detailed visual description of how this person/creature always looks (age, face, hair, clothing, build) so they stay identical across shots"}
  ],
  "scenes": [
    {
      "id": "s1",
      "characters": ["Name"],
      "image_prompt": "a complete, standalone visual description of this single shot (subject, setting, lighting, mood, camera framing). Do not reference other shots.",
      "motion_prompt": "what moves in this shot: camera move + subject motion, kept simple and physical"
    }
  ]
}

Rules:
- One scene = one continuous visual shot. Aim for 4-8 scenes for a short script.
- Keep the scenes in the correct narrative ORDER.
- Only list a character in "characters" if the SAME person should look identical across multiple shots.
- image_prompt must be self-contained and cinematic. motion_prompt must be short and concrete."""


def direct_script(script_text):
    client = Anthropic()
    msg = client.messages.create(
        model=DIRECTOR_MODEL, max_tokens=4000,
        system=DIRECTOR_SYSTEM,
        messages=[{"role": "user", "content": script_text}],
    )
    raw = msg.content[0].text.strip()
    raw = re.sub(r"^```json|^```|```$", "", raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


# ---------- STEP 2: images via Nano Banana (fal) ----------
def gen_anchor(description, aspect):
    res = fal_call(IMAGE_T2I, {
        "prompt": (f"Character reference sheet, front view, plain neutral background, "
                   f"even lighting. {description}"),
        "aspect_ratio": aspect, "num_images": 1, "output_format": "png",
    })
    return res["images"][0]["url"]            # a fal-hosted URL


def gen_scene_image(image_prompt, ref_urls, aspect):
    if ref_urls:                              # keep recurring character(s) consistent
        res = fal_call(IMAGE_EDIT, {
            "prompt": image_prompt, "image_urls": ref_urls,
            "aspect_ratio": aspect, "num_images": 1, "output_format": "png",
        })
    else:                                     # fresh shot, no locked character
        res = fal_call(IMAGE_T2I, {
            "prompt": image_prompt, "aspect_ratio": aspect,
            "num_images": 1, "output_format": "png",
        })
    return res["images"][0]["url"]


# ---------- STEP 3: Wan 2.2 (image URL goes straight in) ----------
def gen_clip(image_url, motion_prompt, aspect):
    res = fal_call(VIDEO_MODEL, {
        "prompt": motion_prompt, "image_url": image_url,
        "resolution": VIDEO_RES, "aspect_ratio": aspect,
    })
    return res["video"]["url"]


# ---------- orchestrator ----------
def run(script_text, size="vertical", project="project"):
    for key in ("FAL_KEY", "ANTHROPIC_API_KEY"):
        if not os.environ.get(key):
            raise SystemExit(f"{key} not set")

    aspect = SIZES.get(size, "9:16")
    out = pathlib.Path("output") / project
    (out / "scenes").mkdir(parents=True, exist_ok=True)
    (out / "clips").mkdir(parents=True, exist_ok=True)

    print("[1/3] Haiku is breaking the script into shots...")
    plan = direct_script(script_text)
    scenes = plan["scenes"]
    log(f"title: {plan.get('title')}  |  scenes: {len(scenes)}")

    print("[2/3] locking recurring characters...")
    anchors = {}
    for ch in plan.get("characters", []):
        log(f"character: {ch['name']}")
        anchors[ch["name"]] = gen_anchor(ch["description"], aspect)

    manifest = {"title": plan.get("title"), "size": size, "clips": []}
    shotlist_lines = [f"TITLE: {plan.get('title')}   SIZE: {size}", ""]

    for i, sc in enumerate(scenes, 1):
        n = f"{i:02d}"                          # 01, 02, 03 ... editor order
        print(f"[3/3] clip {i}/{len(scenes)}  ->  {n}.mp4")
        refs = [anchors[name] for name in sc.get("characters", []) if name in anchors]

        log("image (Nano Banana)...")
        img_url = gen_scene_image(sc["image_prompt"], refs, aspect)
        download(img_url, out / "scenes" / f"{n}.png")

        log("clip (Wan 2.2)...")
        clip_url = gen_clip(img_url, sc["motion_prompt"], aspect)
        download(clip_url, out / "clips" / f"{n}.mp4")

        manifest["clips"].append({
            "order": i, "file": f"{n}.mp4",
            "scene": sc["image_prompt"], "motion": sc["motion_prompt"],
        })
        shotlist_lines += [f"{n}.mp4",
                           f"   scene : {sc['image_prompt']}",
                           f"   motion: {sc['motion_prompt']}", ""]

    (out / "shotlist.txt").write_text("\n".join(shotlist_lines))
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))

    zip_path = out / "clips.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for clip in sorted((out / "clips").glob("*.mp4")):
            z.write(clip, arcname=f"clips/{clip.name}")
        z.write(out / "shotlist.txt", arcname="shotlist.txt")

    print(f"\nDONE. Ordered clips: {out / 'clips'}")
    print(f"Handoff zip: {zip_path}")
    return zip_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python engine.py <script.txt> [vertical|landscape|square]")
        sys.exit(1)
    text = pathlib.Path(sys.argv[1]).read_text()
    size = sys.argv[2] if len(sys.argv) > 2 else "vertical"
    run(text, size, project=pathlib.Path(sys.argv[1]).stem)
