"""LCSC parts mapping for OAS — single source of truth for BOM lookup.

Imported by:
  - hardware/kicad/boardgen/_postprocess.py
    (can be used for schematic symbol metadata injection)
  - hardware/kicad/pipeline/oas/22_export_bom_jlcpcb.py
    (for JLCPCB happy-path BOM post-process: fills LCSC Part #,
    JLCPCB_Library tier, expands designator ranges)

Schema:
    (Value, Footprint) -> {
        "lcsc":         LCSC SKU,
        "manufacturer": "...",
        "mpn":          "...",
        "library":      "Basic" | "Extended" | "N/A",
        "stock":        free-form availability hint,
        "datasheet":    URL,
        "notes":        free-form engineering rationale + audit history,
    }

`Footprint` uses the canonical KiCad library prefix
(e.g. "Capacitor_SMD:C_0603_1608Metric" or "oas:SK6812-SIDE") matching what
boardgen emits into each schematic symbol's "Footprint" property. Stage
22 reads that property out of `kicad-cli sch export bom` and does the
lookup against this dict.

Editing: when the BOM changes (component swap, supplier swap, value tweak),
update the dict ENTRY here, then re-run `python build.py`. Stage 31
(`pipeline/jlcpcb/31_export_bom.py`) writes hardware/output/jlcpcb/oas-BOM.csv
in JLCPCB happy-path format. Any unmapped (Value, Footprint) SMD row triggers
HARD ERROR — catch missing coverage before submitting the JLCPCB quote.
"""

LCSC_MAPPING = {
    ("47nF", "Capacitor_SMD:C_0603_1608Metric"): {
        "lcsc": "C1622",
        "manufacturer": "Samsung Electro-Mechanics",
        "mpn": "CL10B473KB8NNNC",
        "library": "Basic",
        "stock": ">1M",
        "datasheet": "https://www.lcsc.com/datasheet/C1622.pdf",
        "notes": "47nF 50V X7R 10% MLCC. Used as C8 buck-2 BOOT cap.",
    },
    ("100nF", "Capacitor_SMD:C_0603_1608Metric"): {
        "lcsc": "C14663",
        "manufacturer": "Yageo",
        "mpn": "CC0603KRX7R9BB104",
        "library": "Basic",
        "stock": ">1M",
        "datasheet": "https://www.lcsc.com/datasheet/C14663.pdf",
        "notes": "100nF 50V X7R 10% MLCC. C7 + C10..C17 decoupling.",
    },
    ("100nF", "Capacitor_SMD:C_0402_1005Metric"): {
        "lcsc": "C1525",
        "manufacturer": "Samsung Electro-Mechanics",
        "mpn": "CL05B104KO5NNNC",
        "library": "Basic",
        "stock": ">40M",
        "datasheet": "https://www.lcsc.com/datasheet/C1525.pdf",
        "notes": "100nF 16V X7R 10% MLCC 0402. C20-C22/C24-C31 SK6812 LED decoupling. 16V adequate for 5V rail.",
    },
    ("1k", "Resistor_SMD:R_0603_1608Metric"): {
        "lcsc": "C21190",
        "manufacturer": "UNI-ROYAL (Uniroyal Elec)",
        "mpn": "0603WAF1001T5E",
        "library": "Basic",
        "stock": ">5M",
        "datasheet": "https://www.lcsc.com/datasheet/C21190.pdf",
        "notes": "1k 1% 100mW 0603. R4 gate-source clamp current limit.",
    },
    ("100k 1%", "Resistor_SMD:R_0603_1608Metric"): {
        "lcsc": "C25803",
        "manufacturer": "UNI-ROYAL (Uniroyal Elec)",
        "mpn": "0603WAF1003T5E",
        "library": "Basic",
        "stock": ">9M",
        "datasheet": "https://www.lcsc.com/datasheet/C25803.pdf",
        "notes": "100k 1% 100mW 0603. R1 Q1 gate pull-down AND R2 TPS62933 FB top (v0.36 — was 44.2k pre-fix).",
    },
    ("10k 1%", "Resistor_SMD:R_0603_1608Metric"): {
        "lcsc": "C25804",
        "manufacturer": "UNI-ROYAL (Uniroyal Elec)",
        "mpn": "0603WAF1002T5E",
        "library": "Basic",
        "stock": ">11M",
        "datasheet": "https://www.lcsc.com/datasheet/C25804.pdf",
        "notes": "10k 1% 100mW 0603. R7 GPIO8 boot-strap pull-up. (Pre-v0.36 R3 was also 10k; now R3=30.9k.)",
    },
    ("30.9k 1%", "Resistor_SMD:R_0603_1608Metric"): {
        "lcsc": "C23022",
        "manufacturer": "UNI-ROYAL (Uniroyal Elec)",
        "mpn": "0603WAF3092T5E",
        "library": "Extended",
        "stock": ">500k",
        "datasheet": "https://www.lcsc.com/datasheet/C23022.pdf",
        "notes": (
            "30.9k 1% 100mW 0603. R3 TPS62933 FB bottom. With R2=100k yields "
            "Vout=0.8*(1+100/30.9)=3.39V at TPS62933 Vref=0.8V. v0.40 post-order: "
            "VERIFIED CORRECT SKU = C23022. Previous mapping had C23116 which "
            "JLCPCB's database mapped to 0603WAF8060T5E (806 Ohm) — would have "
            "destroyed 3V3 rail (Vout would saturate at 22V). Caught at JLCPCB "
            "Assembly Order XLS cross-check pre-payment; corrected via Select "
            "by Customer override."
        ),
    },
    ("10nF Y2", "Capacitor_SMD:C_0805_2012Metric"): {
        "lcsc": "C97925",
        "manufacturer": "Murata Electronics",
        "mpn": "GRM21BR72A103KA01L",
        "library": "Extended",
        "stock": ">9 JLCPCB warehouse (v0.40 order check)",
        "datasheet": "https://www.lcsc.com/datasheet/C97925.pdf",
        "notes": (
            "SUBSTITUTION FLAG: 10nF 100VDC X7R 10% 0805 (NOT Y2-safety-certified). "
            "True Y2-class MLCC unavailable in 0805 SMD form factor. For 24V DC SELV "
            "system in fully-isolated plastic AK-N-94 enclosure this is electrically "
            "equivalent (PE conductor terminates at PCB GND via this cap for EMI "
            "bridge only; no hazardous mains potential bridged). 100V rating = 4x "
            "derating over 24V SELV. v0.40 post-order: switched from Walsin C303895 "
            "(250V but only 1 unit JLCPCB warehouse stock at order time) to Murata "
            "GRM21BR72A103KA01L (100V 9 units stock). If strict Y2 certification "
            "required change footprint to 1812 and source Knowles/KEMET CAS series."
        ),
    },
    ("10uF 25V", "Capacitor_SMD:C_0805_2012Metric"): {
        "lcsc": "C15850",
        "manufacturer": "Samsung Electro-Mechanics",
        "mpn": "CL21A106KAYNNNE",
        "library": "Basic",
        "stock": ">3M",
        "datasheet": "https://www.lcsc.com/datasheet/C15850.pdf",
        "notes": "10uF 25V X5R 10% 0805. C5 buck-2 Vin / C9 buck-2 Vout. 25V rating exceeds 16V spec.",
    },
    ("10V Zener 200mW", "Diode_SMD:D_SOD-323"): {
        "lcsc": "C19334",
        "manufacturer": "Nanjing Semtech Electronics",
        "mpn": "BZT52C10S",
        "library": "Extended",
        "stock": ">20k",
        "datasheet": "https://www.lcsc.com/datasheet/C19334.pdf",
        "notes": (
            "D3 Q1 Vgs clamp. v0.36 swap PMV65XP -> AO3401A exposed AO3401A "
            "Vgs_max=+/-12V; 10V Zener clamps Vgs at -10V (2V margin under +/-12V "
            "limit AND optimal Rds_on operating point: 60 mOhm at Vgs=-10V). v0.40 "
            "post-order MATH FIX: Q1 MOSFET gate is DC high-impedance (Igss <= 100 nA) "
            "so I_R4 = 0 in steady state — all Zener leakage current flows through R1 "
            "(100 kOhm gate pulldown) NOT R4 (1 kOhm gate series). I_z = (24V-10V)/R1 "
            "= 0.14 mA -> P_D3 = 1.4 mW steady state — 143x under-rated vs 200 mW "
            "SOD-323 limit. VERIFIED CORRECT SKU = C19334. Previous mapping had C8492 "
            "which JLCPCB smart-matched to LBSS84LT1G P-Channel MOSFET in SOT-23 — "
            "wrong device class AND wrong footprint. Caught at Assembly Order XLS "
            "cross-check pre-payment; corrected via Select by Customer override."
        ),
    },
    ("2.2uH 2A", "Inductor_SMD:L_Cenker_CKCS5040"): {
        "lcsc": "C354602",
        "manufacturer": "CENKER",
        "mpn": "CKCS5040-2.2uH/M",
        "library": "Extended",
        "stock": ">50k",
        "datasheet": "https://www.lcsc.com/datasheet/C354602.pdf",
        "notes": "2.2uH 5040 shielded inductor. L2 TPS62933 buck-2 output. Rated current typ ~3A for low-uH values — meets 2A requirement.",
    },
    ("22uF 10V", "Capacitor_SMD:C_0805_2012Metric"): {
        "lcsc": "C45783",
        "manufacturer": "Samsung Electro-Mechanics",
        "mpn": "CL21A226MAQNNNE",
        "library": "Basic",
        "stock": ">2M",
        "datasheet": "https://www.lcsc.com/datasheet/C45783.pdf",
        "notes": "22uF 25V X5R 20% 0805. C6 buck-2 output bulk. 25V rating exceeds 10V spec.",
    },
    ("33uH 2A", "Inductor_SMD:L_Cenker_CKCS5040"): {
        "lcsc": "C354612",
        "manufacturer": "CENKER",
        "mpn": "CKCS5040-33uH/M",
        "library": "Extended",
        "stock": ">30k",
        "datasheet": "https://www.lcsc.com/datasheet/C354612.pdf",
        "notes": (
            "FLAG: 33uH 5040 shielded inductor Irms=1.2A Isat=1.3A — BELOW the 2A "
            "target. Physical limit at 5x5mm body. For prototype 5 units this is "
            "adequate because typical OAS load is ~300mA (LD2410 80mA + LED ring "
            "avg 80mA + SEN66 130mA + misc) — well within 1.2A Irms. If load "
            "increases substantially in production switch L1 footprint to 6045 or "
            "1264 (12x12mm) and use Bourns SRR1260-330M (C840528 3A 33uH). LM2596 "
            "frequency 150 kHz means current ripple at 1A load ~480mAp-p which is "
            "below 1.3A Isat with margin."
        ),
    },
    ("4.7k 1%", "Resistor_SMD:R_0603_1608Metric"): {
        "lcsc": "C23162",
        "manufacturer": "UNI-ROYAL (Uniroyal Elec)",
        "mpn": "0603WAF4701T5E",
        "library": "Basic",
        "stock": ">10M",
        "datasheet": "https://www.lcsc.com/datasheet/C23162.pdf",
        "notes": "4.7k 1% 100mW 0603. R5/R6 I2C pull-ups (4.7k chosen per v0.22 for ~220mm bus length rise-time spec).",
    },
    ("44.2k 1%", "Resistor_SMD:R_0603_1608Metric"): {
        "lcsc": "DEPRECATED-v0.36",
        "manufacturer": "N/A",
        "mpn": "N/A",
        "library": "N/A",
        "stock": "N/A",
        "datasheet": "N/A",
        "notes": (
            "DEPRECATED in v0.36. Pre-fix this was R2 with R3=10k computed against "
            "the WRONG Vref=0.6V assumption. Actual TPS62933 Vref=0.8V; the 44.2k/10k "
            "pair would produce 4.34V and destroy ESP32-C6 + SEN66. R2 is now 100k "
            "and R3 is 30.9k. This entry retained only so the BOM post-process matcher "
            "doesn't trip on a stale Value lookup if someone regenerates from a "
            "pre-v0.36 schematic."
        ),
    },
    ("JST SH SM04B-SRSS-TB (Qwiic / Stemma QT)", "Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal"): {
        "lcsc": "C160404",
        "manufacturer": "JST Sales America",
        "mpn": "SM04B-SRSS-TB(LF)(SN)",
        "library": "Extended",
        "stock": ">20k",
        "datasheet": "https://www.lcsc.com/datasheet/C160404.pdf",
        "notes": "Genuine JST SH 4-pin horizontal SMD socket. J9 Qwiic/Stemma QT port.",
    },
    ("JST SM06B-GHS-TB (SEN66-SIN-T, MPN 3.001.030; TME/Mouser)", "Connector_JST:JST_GH_SM06B-GHS-TB_1x06-1MP_P1.25mm_Horizontal"): {
        "lcsc": "C133065",
        "manufacturer": "JST Sales America",
        "mpn": "SM06B-GHS-TB(LF)(SN)",
        "library": "Extended",
        "stock": ">3k",
        "datasheet": "https://www.lcsc.com/datasheet/C133065.pdf",
        "notes": "Genuine JST GH 6-pin horizontal SMD socket. J3 SEN66 connector — must be genuine JST (not clone) for Sensirion cable compatibility.",
    },
    ("LM2596S-5.0", "oas:TO-263-5_LM2596"): {
        "lcsc": "C116713",
        "manufacturer": "Texas Instruments",
        "mpn": "LM2596S-5.0/NOPB",
        "library": "Extended",
        "stock": ">5k",
        "datasheet": "https://www.ti.com/lit/ds/symlink/lm2596.pdf",
        "notes": "U1 5V buck. Official TI part. Lower-cost UMW clone available at C347421 (~$0.27 vs ~$1.10) — substitute if cost-sensitive but TI original recommended.",
    },
    ("AO3401A", "Package_TO_SOT_SMD:SOT-23"): {
        "lcsc": "C15127",
        "manufacturer": "Alpha & Omega Semiconductor",
        "mpn": "AO3401A",
        "library": "Extended",
        "stock": ">500k",
        "datasheet": "https://www.lcsc.com/datasheet/C15127.pdf",
        "notes": (
            "v0.36 SUBSTITUTION: AO3401A replaces PMV65XP. PMV65XP Vds_max=-20V was "
            "exceeded by the SMBJ24A 38.9V clamp voltage. AO3401A: P-MOSFET SOT-23 "
            "(same footprint), Vds_max=-30V — but the 38.9V worst-case TVS clamp "
            "event EXCEEDS Vds_max by 8.9V (i.e. -8.9V OVERSTRESS during a worst-case "
            "surge). Steady-state operation has Vds ~ 0V (Q1 in deep conduction); "
            "the overstress condition is transient-only (SMBJ24A 600W ~ms-duration "
            "surge clamp). Documented residual risk on the prototype — for production "
            "reliability the recommended substitute is AON7415 (Vds_max=-40V, drop-in "
            "SOT-23). Vgs_max=+/-12V, Id=-4A continuous, RDS(on)=60mOhm @ Vgs=-10V. "
            "Pin order 1=G, 2=S, 3=D (same as PMV65XP — drop-in)."
        ),
    },
    ("PTC 750mA / 33V", "oas:Fuse_1812L_4532Metric"): {
        "lcsc": "C151170",
        "manufacturer": "Littelfuse",
        "mpn": "1812L075/33DR",
        "library": "Extended",
        "stock": ">12k",
        "datasheet": "https://www.lcsc.com/datasheet/C151170.pdf",
        "notes": (
            "F1 input PTC polyfuse, 1812 SMD. Littelfuse 1812L075/33DR: 33 V, "
            "0.75 A hold / 1.5 A trip. 33 V gives comfortable margin on the 24 V "
            "SELV rail (input transients clamped by D1 SMBJ24A TVS); the 1812L075 "
            "family tops out at 33 V — 60 V needs the larger 2920 body. "
            "v0.42 (2026-05-20) CORRECTION: the previous entry carried LCSC "
            "C262023 labelled 'Littelfuse 1812L075THDR' — but C262023 is actually "
            "TLC-MSMD050, a 15 V / 500 mA fuse (verified via EasyEDA + LCSC), "
            "under-rated for the 24 V rail. Caught by the pre-order cross-check "
            "per Lesson 5. Footprint is project-local oas:Fuse_1812L_4532Metric: "
            "KiCad stock Fuse_1812_4532Metric is a generic IPC land (pad gap "
            "3.15 mm) that mismatched this part's terminal geometry (gap "
            "2.30 mm) -> JLCPCB DFM 'pin inner edge'. 3D model: KiCad stock "
            "`Resistor_SMD.3dshapes/R_1812_4532Metric.step` surrogate."
        ),
    },
    ("SK6812-SIDE", "oas:SK6812-SIDE"): {
        "lcsc": "C5378721",
        "manufacturer": "OPSCO Optoelectronics",
        "mpn": "SK6812SIDE-A",
        "library": "Extended",
        "stock": ">238k",
        "datasheet": "https://www.lcsc.com/datasheet/C5378721.pdf",
        "notes": "D11-D22 (11 LEDs) AQI ring. PINOUT-VERIFIED: 1=DIN 2=VDD 3=DOUT 4=GND matches oas:SK6812-SIDE footprint. NOT the -RVS variant. Massive stock at JLCPCB (238k+).",
    },
    ("SMBJ24A", "Diode_SMD:D_SMB"): {
        "lcsc": "C87268",
        "manufacturer": "Brightking",
        "mpn": "SMBJ24A",
        "library": "Basic",
        "stock": ">29k",
        "datasheet": "https://www.lcsc.com/datasheet/C87268.pdf",
        "notes": "D1 TVS diode 24V unidirectional SMB. Vbr=26.7V Vcl=38.9V at 15.4A 600W. Alternative: C135060 (Diodes Inc original) if Brightking unavailable.",
    },
    ("SS14", "Diode_SMD:D_SMA"): {
        "lcsc": "C2480",
        "manufacturer": "MDD (Microdiode Semiconductor)",
        "mpn": "SS14",
        "library": "Basic",
        "stock": ">5M",
        "datasheet": "https://www.lcsc.com/datasheet/C2480.pdf",
        "notes": "D2 Schottky 40V 1A SMA for buck-1 freewheel. Very common Basic part.",
    },
    ("TPS62933", "Package_TO_SOT_SMD:SOT-583-8"): {
        "lcsc": "C3200405",
        "manufacturer": "Texas Instruments",
        "mpn": "TPS62933DRLR",
        "library": "Extended",
        "stock": ">30k",
        "datasheet": "https://www.ti.com/lit/ds/symlink/tps62933.pdf",
        "notes": "U2 sync buck SOT-583-8. 3.8-30V input 3A 800mV-22V output adjustable.",
    },
}
