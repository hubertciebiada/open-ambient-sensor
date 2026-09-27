"""Soundtrack for the OAS brag video: music + sound effects written as one piece.

Key of D major / B minor. Free-time intro, then 106.67 bpm (beat 0.5625 s) from
the reveal, so every scene cut lands on a bar line. Effects are tuned to the
chords and share the music's reverb. Writes soundtrack.wav (48 kHz stereo).
"""
import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 48000
DUR = 20.0
N = int(SR * DUR)
rng = np.random.default_rng(20260927)

# ---- timeline (must match comp.js) -------------------------------------------------
TB, TC, TD, TE = 3.0, 7.5, 12.0, 16.5
BEAT = 0.5625
PASS_T = TD + 5.5 * BEAT                  # 15.09375
CHIP_T = [TB + 2 * BEAT, TB + 3 * BEAT, TB + 4 * BEAT]   # SEN66, radar, ESP32
TOAST_T = TC + 5 * BEAT                   # 10.3125
WORD_T = [0.1 + i * 0.06 for i in range(6)]
PURPOSE_T = 1.4
IRIS_T = TB - 0.2                         # the cover goes x-ray
TRACE_T = TD - 0.24                       # the blueprint rim is traced over the cover
FLY_T = TE - 0.36                         # the seven LEDs leave the board
HALO_T = TE + 0.3                         # the perforation halo lights outward
LINE_T = [PASS_T - (35 - i) * (BEAT / 8) for i in range(35)]
TYPE_T = [TD + 0.28 + (i + 0.5) * 0.3 / 15 for i in range(15)]
WORDMARK_T = TE + 0.35


def spring_def(x):
    """The composition's "def" spring (1.5 Hz, damping 0.9) as a unit step response."""
    w, z = 2 * np.pi * 1.5, 0.9
    wd = w * np.sqrt(1 - z * z)
    x = np.maximum(x, 0)
    return 1 - np.exp(-z * w * x) * (np.cos(wd * x) + (z * w / wd) * np.sin(wd * x))


# landing time of each LED = when its spring reaches 92 % (same order as comp.js: clockwise from top)
_xs = np.arange(0, 1.5, 1e-4)
LAND_DT = _xs[np.argmax(spring_def(_xs) >= 0.92)]
LED_PAN = [0.0, 0.28, 0.33, 0.35, -0.35, -0.33, -0.28]
LAND_T = [FLY_T + i * 0.05 + LAND_DT for i in range(7)]


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def tt(n):
    return np.arange(n) / SR


def bus():
    return np.zeros((2, N))


def place(dst, x, t0, pan=0.0, gain=1.0):
    """Mix mono or stereo x into dst at time t0 (equal-power pan for mono)."""
    i0 = int(round(t0 * SR))
    if x.ndim == 1:
        a = np.pi / 4 * (pan + 1)
        x = np.vstack([x * np.cos(a), x * np.sin(a)]) * np.sqrt(2)
    if i0 < 0:
        x = x[:, -i0:]
        i0 = 0
    n = min(x.shape[1], N - i0)
    if n > 0:
        dst[:, i0:i0 + n] += gain * x[:, :n]


def env_ar(n, a, r_tau):
    t = tt(n)
    return (1 - np.exp(-t / max(a, 1e-4))) * np.exp(-t / r_tau)


def saw_blep(f, n, ph0):
    dt = f / SR
    ph = (ph0 + dt * np.arange(n)) % 1.0
    y = 2 * ph - 1
    m = ph < dt
    x = ph[m] / dt
    y[m] -= x + x - x * x - 1
    m = ph > 1 - dt
    x = (ph[m] - 1) / dt
    y[m] -= x * x + x + x + 1
    return y


def lowpass_varying(x, cutoff, q=0.707, block=128):
    """Block-wise RBJ low-pass with a time-varying cutoff (Hz per sample)."""
    out = np.zeros_like(x)
    zi = [np.zeros(2), np.zeros(2)]
    for s in range(0, x.shape[1], block):
        e = min(s + block, x.shape[1])
        fc = float(np.clip(cutoff[s], 40, SR * 0.45))
        w0 = 2 * np.pi * fc / SR
        al = np.sin(w0) / (2 * q)
        cw = np.cos(w0)
        b = np.array([(1 - cw) / 2, 1 - cw, (1 - cw) / 2])
        a = np.array([1 + al, -2 * cw, 1 - al])
        b, a = b / a[0], a / a[0]
        for ch in range(x.shape[0]):
            out[ch, s:e], zi[ch] = signal.lfilter(b, a, x[ch, s:e], zi=zi[ch])
    return out


def curve(points):
    """Piecewise-linear automation from (time, value) points, per sample."""
    ts, vs = zip(*points)
    return np.interp(tt(N), ts, vs)


def ease_inout3(x):
    x = np.clip(x, 0, 1)
    return np.where(x < 0.5, 4 * x ** 3, 1 - (-2 * x + 2) ** 3 / 2)


def ease_out3(x):
    x = np.clip(x, 0, 1)
    return 1 - (1 - x) ** 3


# ---- the air in scene C (same profile as the video) ----------------------------------
def co2_at(t):
    tc = t - TC
    return np.select(
        [tc < 0.6, tc < 2.6, tc < 2.9, tc < 4.2],
        [640, 640 + 540 * ease_inout3((tc - 0.6) / 2.0), 1180, 1180 - 460 * ease_out3((tc - 2.9) / 1.3)],
        720,
    )


# ---- firmware breath (hook) ------------------------------------------------------------
P_LO = 0.2 ** (1 / 2.8)


def breath_k(t):
    s = 0.5 - 0.5 * np.cos(2 * np.pi * ((t + 0.4) % 4) / 4)
    return (P_LO + (1 - P_LO) * s) ** 2.8


# ---- harmony ---------------------------------------------------------------------------
Bm9 = [59, 62, 66, 69, 73]
Dmaj9 = [62, 66, 69, 73, 76]
Gmaj9 = [55, 59, 62, 66, 69]
A69 = [57, 61, 64, 66, 71]
CHORDS = [  # (start, end, pad notes, bass root)
    (0.0, TB, Bm9, 35),
    (TB, TB + 4 * BEAT, Dmaj9, 38),
    (TB + 4 * BEAT, TC, Gmaj9, 31),
    (TC, TC + 4 * BEAT, Bm9, 35),
    (TC + 4 * BEAT, TOAST_T, A69, 33),
    (TOAST_T, TD, Dmaj9, 38),
    (TD, TD + 2 * BEAT, Gmaj9, 31),
    (TD + 2 * BEAT, TD + 4 * BEAT, A69, 33),
    (TD + 4 * BEAT, PASS_T, Bm9, 35),
    (PASS_T, DUR, Dmaj9, 38),
]


def chord_at(t):
    for c in CHORDS:
        if c[0] <= t < c[1]:
            return c
    return CHORDS[-1]


# =========================================================================================
pad, bass, drums, arp, fx = bus(), bus(), bus(), bus(), bus()

# ---- pad: detuned polyBLEP saws, cross-faded chords ------------------------------------------
for ci, (t0, t1, notes, _) in enumerate(CHORDS):
    atk = 1.1 if ci == 0 else 0.45
    rel = 0.9
    n = int((t1 - t0 + rel + 0.1) * SR)
    t = tt(n)
    env = np.clip(t / atk, 0, 1) ** 1.5
    tail = np.clip(1 - (t - (t1 - t0)) / rel, 0, 1)
    env = env * np.where(t < t1 - t0, 1.0, tail ** 2)
    if ci == len(CHORDS) - 1:
        env *= np.clip(1 - (t - (DUR - t0 - 1.4)) / 1.4, 0, 1)
    for m in notes:
        for det, pan in ((-7, -0.55), (0, 0.0), (7, 0.55)):
            f = mtof(m) * 2 ** (det / 1200)
            v = saw_blep(f, n, rng.random()) * 0.33
            v += 0.5 * np.sin(2 * np.pi * f / 2 * t + rng.random() * 6)  # sub-octave warmth
            place(pad, v * env * 0.075, t0, pan)

tv = tt(N)
k = breath_k(tv)
co2 = co2_at(tv)
stale = np.clip((co2 - 640) / 540, 0, 1) * (tv >= TC) * (tv < TOAST_T)
stale += (tv >= TOAST_T) * (tv < TOAST_T + 0.4) * np.clip(1 - (tv - TOAST_T) / 0.4, 0, 1) * 1.0
pad_cut = np.select(
    [tv < TB, tv < TC, tv < TD, tv < TE],
    [600 + 1500 * k, 2600 + 900 * np.clip((tv - TB) / 2, 0, 1), 3200 - 2600 * stale + 1800 * (tv >= TOAST_T + 0.4), 2400 + 3600 * np.clip((tv - TD) / (PASS_T - TD), 0, 1)],
    4200 - 2000 * np.clip((tv - TE) / 3.5, 0, 1),
)
pad = lowpass_varying(pad, pad_cut, q=0.9)
pad *= (0.55 + 0.45 * k)[None, :] * (tv < TB) + (tv >= TB)  # the intro breathes with the ring

# ---- bass: sine + a touch of 2nd harmonic, rhythm from the reveal on ----------------------------
def bass_note(f, dur, vel=1.0):
    n = int(dur * SR)
    t = tt(n)
    e = (1 - np.exp(-t / 0.006)) * np.exp(-t / (dur * 0.9)) * np.clip((dur - t) / 0.03, 0, 1)
    ph = 2 * np.pi * f * t
    return vel * e * (np.sin(ph) + 0.18 * np.sin(2 * ph) + 0.05 * np.sin(3 * ph))


place(bass, bass_note(mtof(35), TB + 0.2, 0.35) * np.clip(tt(int((TB + 0.2) * SR)) / 1.5, 0, 1), 0.0)
t = TB
while t < DUR - 0.05:
    c = chord_at(t + 1e-6)
    beat_i = round((t - TB) / BEAT)
    f = mtof(c[3])
    if TD <= t < TE:          # driving 8ths in the brag
        place(bass, bass_note(f, BEAT / 2 * 0.92, 0.8 if beat_i % 2 == 0 else 0.62), t)
        place(bass, bass_note(f, BEAT / 2 * 0.92, 0.55), t + BEAT / 2)
    elif t >= TE:
        if abs(t - TE) < 1e-6:
            place(bass, bass_note(f, 3.3, 0.5), t)
    else:
        pos = beat_i % 4
        if pos == 0:
            place(bass, bass_note(f, BEAT * 1.4, 0.9), t)
        elif pos == 1:
            place(bass, bass_note(f, BEAT * 0.45, 0.5), t + BEAT / 2)
        elif pos == 2:
            place(bass, bass_note(f * (1.5 if c[3] != 31 else 2 ** (7 / 12)), BEAT * 0.9, 0.55), t)
    t += BEAT
bass = lowpass_varying(bass, np.full(N, 900.0), q=0.7)

# ---- drums -------------------------------------------------------------------------------------
def kick(vel=1.0):
    n = int(0.42 * SR)
    t = tt(n)
    f = 44 + 80 * np.exp(-t * 32)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 7.5) * (1 - np.exp(-t / 0.001))
    click = signal.lfilter(*signal.butter(2, 3500 / (SR / 2)), rng.standard_normal(n)) * np.exp(-t * 260) * 0.12
    return vel * (body + click)


hp = signal.butter(4, 7200 / (SR / 2), "high")


def hat(vel=1.0, decay=0.035):
    n = int(0.12 * SR)
    t = tt(n)
    y = signal.lfilter(*hp, rng.standard_normal(n)) * np.exp(-t / decay) * (1 - np.exp(-t / 0.0006))
    return vel * y


kick_times = []
t = TB
while t < TE + 0.01:
    beat_i = round((t - TB) / BEAT)
    pos = beat_i % 4
    in_c_quiet = TC <= t < TOAST_T
    if abs(t - TB) < 1e-6:
        kick_times.append((t, 1.0))
    elif TD <= t < TE:
        kick_times.append((t, 0.82))
    elif abs(t - TE) < 1e-6:
        kick_times.append((t, 0.95))
    elif pos in (0, 2) and t < TE:
        kick_times.append((t, 0.6 if in_c_quiet else 0.75))
    # hats
    if t < TE:
        if TD <= t:
            for s16 in range(4):
                place(drums, hat((0.06, 0.08, 0.13, 0.08)[s16], 0.026), t + s16 * BEAT / 4, pan=0.25)
        elif not in_c_quiet or t < TC + 1.0:
            place(drums, hat(0.13 * (1 - 0.8 * float(stale[int(t * SR)])), 0.04), t + BEAT / 2, pan=0.22)
    t += BEAT
for kt, kv in kick_times:
    place(drums, kick(kv), kt)

# kick-driven ducking for pad/bass/arp (subtle pump)
duck = np.ones(N)
for kt, kv in kick_times:
    i0 = int(kt * SR)
    n = int(0.3 * SR)
    d = 1 - 0.32 * kv * np.exp(-tt(n) / 0.09)
    e = min(N, i0 + n)
    duck[i0:e] = np.minimum(duck[i0:e], d[: e - i0])

# ---- arp: soft plucks through a ping-pong delay ---------------------------------------------------
def pluck(f, vel=1.0, tau=0.2):
    n = int(0.9 * SR)
    t = tt(n)
    e = (1 - np.exp(-t / 0.0015)) * np.exp(-t / tau)
    y = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t) * np.exp(-t / 0.05) + 0.08 * np.sin(6 * np.pi * f * t) * np.exp(-t / 0.025)
    return vel * e * y


# hook: one soft harp note per word (Bm9, rising), then F#5 under "On purpose."
for i, wt in enumerate(WORD_T):
    place(arp, pluck(mtof([59, 62, 66, 69, 73, 74][i]), 0.28, 0.35), wt, pan=-0.3 + 0.12 * i)
t = TB
while t < TE - 0.01:
    c = chord_at(t + 1e-6)
    notes = sorted(c[2]) + [c[2][1] + 12]
    step = BEAT / 4 if TD <= t else BEAT / 2
    i = int(round((t - TB) / step))
    pattern = [0, 2, 4, 1, 3, 5, 2, 4]
    m = notes[pattern[i % len(pattern)] % len(notes)] + 12
    vel = (0.34 if TD <= t else 0.26) * (1 - 0.7 * float(stale[int(t * SR)]))
    if not (TD <= t < TD + 0.5):
        place(arp, pluck(mtof(m), vel, 0.12 if TD <= t else 0.18), t, pan=0.35 if i % 2 else -0.35)
    t += step
# outro: slow rising Dmaj9 arpeggio
for i, m in enumerate([74, 78, 81, 85, 88]):
    place(arp, pluck(mtof(m), 0.24, 0.5), TE + 2.25 + i * BEAT / 2, pan=-0.4 + 0.2 * i)

# ping-pong delay (dotted 8th)
dly = int(0.75 * BEAT * SR)
arp_d = np.zeros_like(arp)
fb = 0.32
for rep in range(1, 5):
    g = fb ** rep
    sh = dly * rep
    src = arp[::-1] if rep % 2 else arp
    arp_d[:, sh:] += g * src[:, :-sh]
arp = arp + arp_d
arp_cut = 7000 - 5800 * stale
arp = lowpass_varying(arp, arp_cut, q=0.8)

# ---- fx: bells, chime, whooshes, ticks ------------------------------------------------------------
def bell(f, vel=1.0, ratio=2.0, index=1.6, decay=1.1):
    n = int((decay * 5 + 0.1) * SR)
    t = tt(n)
    idx = index * np.exp(-t / 0.35)
    y = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * ratio * t))
    y += 0.25 * np.sin(2 * np.pi * f * 2.0 * t) * np.exp(-t / (decay * 0.4))
    return vel * y * (1 - np.exp(-t / 0.002)) * np.exp(-t / decay)


place(fx, bell(mtof(78), 0.3, 2.0, 1.2, 1.2), PURPOSE_T, pan=0.1)
for tchip, m in zip(CHIP_T, (78, 81, 86)):
    place(fx, bell(mtof(m), 0.24, 2.0, 1.4, 0.9), tchip, pan={78: 0.3, 81: -0.3, 86: 0.15}[m])
place(fx, bell(mtof(81), 0.26, 2.0, 1.2, 0.6), TOAST_T, pan=0.2)
place(fx, bell(mtof(86), 0.26, 2.0, 1.2, 0.8), TOAST_T + 0.11, pan=0.25)
# PASS: D-major stab
for m, p in ((74, -0.3), (78, 0.3), (81, -0.1), (86, 0.15)):
    place(fx, bell(mtof(m), 0.23, 2.0, 2.0, 1.4), PASS_T, pan=p)
    place(fx, pluck(mtof(m), 0.25, 0.3), PASS_T, pan=-p)
# the ring powers on
place(fx, bell(mtof(74), 0.1, 2.0, 0.8, 1.6), 0.05)
# x-ray: a glassy zing where the iris opens (right of centre)
place(fx, bell(mtof(81), 0.14, 3.5, 1.6, 0.7), IRIS_T, pan=0.35)
# the seven LEDs land in the logomark: one note each, rising through D major
for lt, m, p in zip(LAND_T, (74, 78, 81, 85, 88, 90, 93), LED_PAN):
    place(fx, pluck(mtof(m), 0.2, 0.35), lt, pan=p)
    place(fx, bell(mtof(m), 0.06, 2.0, 0.9, 0.8), lt, pan=p)
# wordmark bell
place(fx, bell(mtof(86), 0.3, 3.5, 1.1, 2.2), WORDMARK_T)
place(fx, bell(mtof(74), 0.22, 2.0, 0.8, 2.6), WORDMARK_T)


def noise_sweep(dur, f0, f1, shape, vel=1.0, q=4.0):
    """Band-passed noise with the centre gliding f0 -> f1 (exponential), amplitude from `shape`."""
    n = int(dur * SR)
    t = tt(n)
    x = rng.standard_normal(n)
    fc = f0 * (f1 / f0) ** (t / dur)
    out = np.zeros(n)
    zi = np.zeros(2)
    blk = 128
    for s in range(0, n, blk):
        e = min(n, s + blk)
        w0 = 2 * np.pi * fc[s] / SR
        al = np.sin(w0) / (2 * q)
        b = np.array([al, 0, -al])
        a = np.array([1 + al, -2 * np.cos(w0), 1 - al])
        out[s:e], zi = signal.lfilter(b / a[0], a / a[0], x[s:e], zi=zi)
    return vel * out * shape(t / dur)


def swell(u):  # rise, then a quick stop at the cut
    return np.clip(u, 0, 1) ** 2.2 * np.clip((1 - u) / 0.06, 0, 1)


# reverse swell into the reveal: a reversed, reverberant D-major bell chord ending at 3.0
rev = np.zeros(int(2.0 * SR))
for m in (62, 66, 69, 74):
    b = bell(mtof(m), 0.25, 2.0, 1.0, 0.9)[: len(rev)]
    rev[: len(b)] += b
rev = signal.lfilter(*signal.butter(2, 5000 / (SR / 2)), rev)[::-1] * np.linspace(0, 1, len(rev)) ** 2
place(fx, rev, TB - len(rev) / SR)
place(fx, noise_sweep(0.75, 500, 4200, swell, 0.08, 3.0), TB - 0.75, pan=0.0)
# zoom-through into the ring (B -> C): whoosh + a shimmer for the flash of light
place(fx, noise_sweep(0.55, 400, 5000, swell, 0.09, 3.0), TC - 0.5)
n = int(0.62 * SR)
shim = signal.lfilter(*signal.butter(2, 5000 / (SR / 2), "high"), rng.standard_normal(n)) * np.sin(np.pi * np.clip(tt(n) / 0.62, 0, 1)) ** 1.6
place(fx, np.vstack([shim, np.roll(shim, 173)]) * 0.035, TC - 0.34)
# C -> D: a pen tone gliding along the rim as it is traced, with a soft brush
n = int(0.86 * SR)
tp = tt(n)
f = mtof(74) * (mtof(81) / mtof(74)) ** (0.5 - 0.5 * np.cos(np.pi * tp / 0.86))
pen = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tp / 0.86) ** 1.2 * 0.05
place(fx, pen, TRACE_T, pan=0.2)
place(fx, noise_sweep(0.86, 2500, 5200, lambda u: np.sin(np.pi * np.clip(u, 0, 1)) ** 2, 0.03, 5.0), TRACE_T, pan=0.2)
# into the outro
place(fx, noise_sweep(0.7, 600, 6000, swell, 0.08, 3.0), TE - 0.68)
# the perforation halo lights outward
n = int(1.1 * SR)
hs = signal.lfilter(*signal.butter(2, 6000 / (SR / 2), "high"), rng.standard_normal(n)) * np.sin(np.pi * np.clip(tt(n) / 1.1, 0, 1)) ** 2
place(fx, np.vstack([hs, np.roll(hs, 97)]) * 0.025, HALO_T)
# PASS shimmer
n = int(1.6 * SR)
sh = signal.lfilter(*signal.butter(2, 6500 / (SR / 2), "high"), rng.standard_normal(n)) * np.exp(-tt(n) / 0.45) * (1 - np.exp(-tt(n) / 0.004))
place(fx, np.vstack([sh, np.roll(sh, 211)]) * 0.05, PASS_T)


def tick(f, vel=1.0):
    n = int(0.03 * SR)
    t = tt(n)
    return vel * np.sin(2 * np.pi * f * t) * np.exp(-t / 0.004) * (1 - np.exp(-t / 0.0004))


for i, lt in enumerate(LINE_T):  # one tick per stage line, alternating D6 / A6, rising a little
    place(fx, tick(mtof(98 if i % 2 else 93), 0.05 + 0.07 * i / 34), lt, pan=0.35 if i % 2 else -0.35)
for i, ty in enumerate(TYPE_T):  # typing `python build.py`
    n = int(0.02 * SR)
    c = signal.lfilter(*signal.butter(2, [1800 / (SR / 2), 5200 / (SR / 2)], "band"), rng.standard_normal(n)) * np.exp(-tt(n) / 0.003)
    place(fx, c * (0.05 + 0.02 * rng.random()), ty, pan=0.1 * rng.standard_normal())

# ---- reverb (one shared space) ---------------------------------------------------------------------
def make_ir(rt60=2.3, pre=0.02):
    n = int((rt60 + pre) * SR)
    t = tt(n)
    decay = np.exp(-6.91 * t / rt60)
    ir = rng.standard_normal((2, n)) * decay
    ir = signal.lfilter(*signal.butter(1, 5500 / (SR / 2)), ir, axis=1)
    ir[:, : int(pre * SR)] = 0
    return ir / np.sqrt(np.sum(ir ** 2, axis=1, keepdims=True))


IR = make_ir()
send = 0.22 * pad + 0.38 * arp + 0.5 * fx + 0.06 * drums + 0.03 * bass
wet = np.vstack([signal.fftconvolve(send[c], IR[c])[:N] for c in range(2)])
wet = signal.lfilter(*signal.butter(2, 180 / (SR / 2), "high"), wet, axis=1)

# ---- mix ------------------------------------------------------------------------------------------------
mix = (1.3 * pad * duck + 0.62 * bass * duck + 0.62 * drums + 0.72 * arp * duck + 0.75 * fx + 0.6 * wet)
mix = signal.lfilter(*signal.butter(2, 14000 / (SR / 2)), mix, axis=1)
mix *= np.interp(tv, [0, TD - 0.2, TD + 0.3, TE - 0.2, TE + 0.9, DUR - 0.8, DUR], [1.0, 1.0, 1.18, 1.18, 1.0, 0.62, 0.5])[None, :]
mix = signal.lfilter(*signal.butter(2, 28 / (SR / 2), "high"), mix, axis=1)
mix *= np.clip(tv / 0.04, 0, 1) * np.clip((DUR - tv) / 0.9, 0, 1) ** 1.5
peak = np.max(np.abs(mix))
mix = mix / peak * 0.9
mix = np.tanh(mix * 1.15) / np.tanh(1.15)
mix *= 0.89 / np.max(np.abs(mix))
wavfile.write("soundtrack.wav", SR, (mix.T * 32767).astype(np.int16))
print("peak", peak, "rms dBFS", 20 * np.log10(np.sqrt(np.mean(mix ** 2)) + 1e-12))

if __name__ == "__main__":
    import sys
    if "--debug" in sys.argv:
        stems = {"pad": 1.3 * pad * duck, "bass": 0.62 * bass * duck, "drums": 0.62 * drums, "arp": 0.72 * arp * duck, "fx": 0.75 * fx, "wet": 0.6 * wet}
        wins = [(0, 3), (3, 7.5), (7.5, 10.3), (10.3, 12), (12, 15.1), (15.1, 16.5), (16.5, 20)]
        for name, s in stems.items():
            row = []
            for a, b in wins:
                seg = s[:, int(a * SR):int(b * SR)] / peak * 0.9
                row.append(f"{20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9):6.1f}")
            print(f"{name:6s}", " ".join(row))
        d = np.abs(np.diff(mix, axis=1)).max(axis=0)
        i = int(np.argmax(d))
        print("max step", d[i], "at", i / SR)
