#!/usr/bin/env bash
# Poster + final mux: bake the poster as frame 0 (replacing it, so the duration
# and audio sync stay the same) and add the soundtrack.
set -euo pipefail
cd "$(dirname "$0")"
POSTER_T=6.300
node capture.js stills "$POSTER_T"
python3 - <<EOF
from PIL import Image
Image.open("stills/t_${POSTER_T}.png").convert("RGB").save("../brag.jpg", quality=92, optimize=True)
EOF
ffmpeg -hide_banner -loglevel error -y \
  -i video_noaudio.mp4 -i "stills/t_${POSTER_T}.png" -i soundtrack.wav \
  -filter_complex "[0:v][1:v]overlay=0:0:enable='eq(n\,0)',format=yuv420p[v];[2:a]volume=-1.6dB[a]" \
  -map "[v]" -map "[a]" \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
  -c:a aac -b:a 192k -ar 48000 -movflags +faststart -t 20 ../brag.mp4
ls -la ../brag.mp4 ../brag.jpg
# contact sheet: one frame every 0.5 s (40 frames, 8 x 5)
ffmpeg -hide_banner -loglevel error -y -i ../brag.mp4 -vf "select='eq(mod(n\,15)\,7)',scale=384:-1,tile=8x5:padding=6:color=0x070b09" -frames:v 1 -q:v 3 ../contact-sheet.jpg
ls -la ../contact-sheet.jpg
# README preview: animated WebP (GitHub autoplays images but strips <video>); frame 0 (the poster) left out so it loops cleanly
ffmpeg -hide_banner -loglevel error -y -i ../brag.mp4 -vf "select='gte(n\,1)',fps=24,scale=1280:-2:flags=lanczos" -an -c:v libwebp_anim -lossless 0 -q:v 80 -compression_level 6 -preset photo -loop 0 ../brag.webp
ls -la ../brag.webp
