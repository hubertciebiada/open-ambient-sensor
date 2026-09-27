# Launch video

A 20-second launch video for Open Ambient Sensor, made with the `/brag-slim` skill from [latent-spaces/brag](https://github.com/latent-spaces/brag).

| File | What it is |
|---|---|
| `brag.mp4` | The video: 1920×1080, 30 fps, H.264 + AAC. Frame 0 is the poster. |
| `brag.jpg` | The poster frame. |
| `brag.webp` | The silent, looping preview shown at the top of the repository README. GitHub autoplays animated images but does not play committed videos. |
| `share-copy.txt` | Post text, ready to paste. |
| `brag-plan.md` | The angle, storyboard, timing and critique notes. |
| `contact-sheet.jpg` | One frame every half second, for a quick look without playing the video. |
| `work/` | The generator sources. Frames, fonts and other intermediates are gitignored. |

Everything on screen comes from this repository. The photo is `hardware/photos/v0.54-mounted-led-ring.jpg` and the board is `hardware/renders/pcb/3d-top.png`, masked to the real Edge.Cuts outline. The blueprint scene draws the real `oas.kicad_pcb` pads and the `oas_routes.py` tracks and vias. The terminal lists the real `pipeline/*/NN_*.py` stage names. The ring colour and breathing follow `firmware/esphome/packages/leds.yaml` and `air-quality.yaml`. The soundtrack is synthesised by `work/make_audio.py`, so it has no third-party samples.

To rebuild, you need Node 22 with Playwright + Chromium, Python 3 with numpy, scipy and Pillow, and ffmpeg with libx264:

```sh
cd brag-output/work
npm install                     # Inter + JetBrains Mono (OFL) for the page
python3 extract_board.py && python3 make_data.py
python3 make_audio.py           # -> soundtrack.wav
node capture.js video video_noaudio.mp4
./finalize.sh                   # -> ../brag.mp4, ../brag.jpg, ../contact-sheet.jpg, ../brag.webp
```
