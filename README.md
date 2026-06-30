# Script → Ordered Clips

Turn a script (any topic) into numbered video clips for a video editor.

**Flow:** script → Haiku writes the shot list → Gemini makes each image →
Wan 2.2 turns each image into a clip → you download a zip of ordered clips.

No stitching. You get `01.mp4`, `02.mp4`, `03.mp4` … in order, plus a
`shotlist.txt` describing each one, ready to hand to an editor.

---

## What's in this folder

| File | What it does |
|------|--------------|
| `engine.py` | The pipeline: Haiku → Gemini → Wan 2.2 → ordered clips + zip |
| `app.py` | Web page: upload script, choose size, download clips (runs jobs in the background) |
| `requirements.txt` | Python dependencies |
| `Dockerfile` | Tells Railway how to build and run it |
| `sample_script.txt` | A short test script |
| `.gitignore` / `.dockerignore` | Keep junk and secrets out of git/builds |

---

## STEP 1 — Get your 3 API keys

| Key | Where to get it |
|-----|-----------------|
| `GEMINI_API_KEY` | https://aistudio.google.com → "Get API key" |
| `FAL_KEY` | https://fal.ai → Dashboard → Keys |
| `ANTHROPIC_API_KEY` | https://console.anthropic.com → API keys |

Keep these somewhere safe. You'll paste them into Railway later.

---

## STEP 2 — Test on your Mac first (do NOT skip)

Cloud debugging is slow. Prove it works locally in 10 minutes first.

Open Terminal in this folder and run, one line at a time:

```bash
pip install -r requirements.txt

export FAL_KEY='your_fal_key'
export ANTHROPIC_API_KEY='your_anthropic_key'
export GEMINI_API_KEY='your_gemini_key'

python engine.py sample_script.txt vertical
```

**Success looks like:** a new folder `output/sample_script/` containing
`clips/01.mp4, 02.mp4, …`, `scenes/`, `shotlist.txt`, and `clips.zip`.

If it errors, copy the error and fix it before deploying. Common ones:
- `... not set` → a key wasn't exported in this terminal session.
- "Gemini returned no image" → its safety filter rejected a prompt; reword the script.

---

## STEP 3 — Test the web page locally (optional but smart)

```bash
pip install uvicorn
uvicorn app:app --reload
```

Open http://127.0.0.1:8000 → paste a short script → choose size →
Generate → wait → "Download clips (zip)".

---

## STEP 4 — Put it on GitHub

The Dockerfile must sit at the **top level** of the repo.

```bash
git init
git add .
git commit -m "script to clips"
git branch -M main
git remote add origin https://github.com/YOUR_NAME/script-to-clips.git
git push -u origin main
```

(Or upload the folder through github.com → New repository → "uploading an existing file".)

---

## STEP 5 — Deploy on Railway

1. Go to https://railway.app → **New Project** → **Deploy from GitHub repo**.
2. Pick your repo. Railway sees the `Dockerfile` and starts building on its own.
   (You don't set a language or a start command — the Dockerfile handles it.)
3. Open your service → **Variables** tab → add all three:
   ```
   GEMINI_API_KEY     = ...
   FAL_KEY            = ...
   ANTHROPIC_API_KEY  = ...
   ```
   Saving triggers an automatic redeploy.
4. Open **Settings → Networking → Generate Domain**.
   You now have a public URL like `https://xxxx.up.railway.app`.

---

## STEP 6 — Use it

Open your Railway URL → paste a script → choose size (Vertical / Landscape /
Square) → **Generate clips**. The page shows "Working…" while it runs, then a
**Download clips (zip)** link.

Unzip → `01.mp4, 02.mp4, …` in order + `shotlist.txt` → hand to your editor.

---

## When something breaks

Railway → your service → **Deployments** → active deployment → **View Logs**.
The job prints its progress live:

```
[1/3] Haiku is breaking the script into shots...
[2/3] locking recurring characters...
[3/3] clip 1/4  ->  01.mp4
```

Whatever step it stops on, and the error text, appears there. Send me that and
I'll give the exact fix.

---

## Things to know (so they don't surprise you)

- **Storage is temporary.** Railway wipes the `output/` folder on every
  redeploy. Download your zip in the same session you generate it. To keep
  videos permanently, push the zip to Cloudinary — small add when you're ready.
- **One job at a time** per instance. Fine for you solo. For many users at once,
  move to a job queue later (same Railway + FastAPI pattern you already use).
- **Cost** is roughly: Haiku (cents) + Gemini images ($0.039 each) + Wan 2.2
  clips. A 4-scene vertical test is well under $1. Start small.
- **Swap models** any time at the top of `engine.py`
  (`DIRECTOR_MODEL`, `IMAGE_MODEL`, `VIDEO_MODEL`).

---

## The exact sequence, one line each

1. Get 3 keys (Gemini, fal, Anthropic).
2. `pip install -r requirements.txt`
3. export the 3 keys.
4. `python engine.py sample_script.txt vertical`  → check `output/.../clips.zip`.
5. Push folder to GitHub.
6. Railway → New Project → Deploy from GitHub repo.
7. Add the 3 keys in Variables.
8. Generate Domain.
9. Open URL → paste script → choose size → Generate → download zip.
