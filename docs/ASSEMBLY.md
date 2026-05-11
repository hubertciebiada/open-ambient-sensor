# Assembly

**Status:** preliminary draft. The full procedure will be written once the first prototype is assembled and validated.

## High-level order

1. Receive the PCB (assembled at JLCPCB with Basic + Extended Library parts)
2. Hand-solder Mouser-sourced parts that JLCPCB cannot stock (if any)
3. Connect the SEN66 module to the PCB via a JST GH 6-pin cable (~50 mm)
4. Install the 3D-printed bracket holding the SEN66 against the inside of the enclosure cover
5. Snap the PCB into the SZOMK AK-N-94 enclosure (PCB rests on the cover screws / posts)
6. Wire 24 V DC to the input terminal block; mount on the wall-recessed electrical box
7. Power on; flash via USB-C (see [`FLASHING.md`](./FLASHING.md))

## Tools needed

- Soldering iron (for any hand-soldered parts)
- Phillips screwdriver (M3)
- USB-C cable for initial flashing

## Mounting

The PCB is a **Ø120 mm D-shape** with 3× M3 mounting holes (Ø3.8 mm) at the positions defined in the SZOMK AK-N-94 dimension DXF. The flat chord (82.6 mm long) is on the **bottom edge** — the connector strip and the sensor inlet face the room below the enclosure.

The completed assembly mounts on a standard wall-recessed electrical box (60 mm screw pitch).

## Safety

- 24 V DC only — never connect mains directly
- TVS + PTC on the input protect against transients and reverse polarity; do not bypass
