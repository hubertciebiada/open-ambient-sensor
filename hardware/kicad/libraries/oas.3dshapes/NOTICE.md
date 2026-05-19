# Third-party 3D model attributions

This directory contains 3D STEP models referenced from the OAS KiCad
project. Each entry below lists the upstream source and license that
governs the bundled file.

## `SK6812-SIDE-A.step`

OPSCO / Normand SK6812 SIDE-A addressable RGB LED (4020 side-emit package,
LCSC C5378721).

Source: <https://github.com/scottbez1/smartknob>
Path in upstream: `electronics/lib/sk6812.3dshapes/SK6812-SIDE-A.step`
Upstream commit: master @ retrieval 2026-05-19

```
Copyright 2022 Scott Bezek
Licensed under the Apache License, Version 2.0
https://www.apache.org/licenses/LICENSE-2.0
```

Used unmodified. The full Apache 2.0 license text is available at the URL
above and from the upstream SmartKnob repository.

## `Polyfuse_2920_7451Metric.step` (NOT PRESENT — historical reference)

Earlier versions of the OAS project (pre-v0.41) used a 2920 SMD polyfuse
(`Fuse:Fuse_2920_7451Metric`) with no permissively-licensed 3D model
available in the KiCad install. v0.41 downsized the polyfuse to 1812
(`Fuse:Fuse_1812_4532Metric`) and reuses the stock KiCad
`Resistor_SMD.3dshapes/R_1812_4532Metric.step` model — same package
dimensions, no bundled file needed. No 2920 STEP is present in this
directory.
