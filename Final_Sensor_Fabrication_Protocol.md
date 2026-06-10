# Flexible Conductive Silicone Pressure Sensor Fabrication Protocol

## Purpose

This document describes the fabrication process used to create a flexible conductive silicone pressure sensor consisting of a conductive polymer composite sheath surrounding silicone tubing and encapsulated within an outer silicone layer.

---

# Sensor Structure

### Layer Description

1. **Silicone Tubing Core** – Fluid path used for pressure transmission.
2. **Conductive Composite Sheath** – Fabricated from silicone, NCCF, BNS, and silicone oil. Changes resistance as the tubing expands.
3. **Outer Silicone Encapsulation** – Protects the conductive layer and improves durability.

### Fabrication Order

1. Insert stainless steel rod into tubing.
2. Mold conductive composite sheath around tubing.
3. Cure conductive composite.
4. Mold outer silicone encapsulation.
5. Final cure and trim excess material.

---

# Materials

## Sensor Materials

- Silicone Rubber Part A (Let's Resin, Hardness 0A)
- Silicone Rubber Part B (Let's Resin, Hardness 0A)
- Precision Coated and Converted Fibers (PC2F / NCCF), Product #1AC1PC-0.5
- Branched Nickel Strands (BNS), Product #3AA150
- Silicone Oil (MicroLubrol Type 200 Fluid Silicone Oil, 50 cSt)

## Fabrication Materials

- Silicone tubing (approximately 3 mm inner diameter and 5 mm outer diameter)
- Trigger clamps
- Stainless steel rod or needle stock sized to fit through the tubing lumen
- Scale
- Vacuum chamber
- Beakers
- Glass stirring rod
- Disposable weighing boats
- Pipettes (tips cut to act as small scoops)
- Scissors
- 3D printed molds

---

# Composite Formulations

## Recipe 1

| Material | Mass (g) |
|-----------|-----------:|
| Silicone Part A | 4.000 |
| Silicone Part B | 4.000 |
| NCCF | 0.528 |
| BNS | 2.202 |
| Silicone Oil | 0.506 |

Total Batch Mass: 11.236 g

## Recipe 2

| Material | Mass (g) |
|-----------|-----------:|
| Silicone Part A | 4.000 |
| Silicone Part B | 4.000 |
| NCCF | 1.330 |
| BNS | 0.413 |
| Silicone Oil | 0.333 |

Total Batch Mass: 10.076 g

Fifty percent of Silicone Part A and Silicone Part B are reserved for fabrication of the outer silicone encapsulation layer.

---

# 3D Printed Components

## Printer Settings

- Printer: Original Prusa XL – 5T Input Shaper
- Nozzle: 0.4 mm
- Filament: Prusa PLA

## Repository Structure

```text
STL/
├── NCCF_Top.STL
├── NCCF_Bottom.STL
├── Silicone_Top.STL
└── Silicone_Bottom.STL

images/
└── Final_Sensor.png
```

---

# Fabrication Procedure

## 1. Prepare Materials

1. Measure all materials by weight according to the selected formulation.
2. Place materials into disposable weighing boats.
3. Cut the ends off pipettes to create small scoops for handling fibers and powders.

## 2. Prepare Conductive Composite

1. Add silicone oil to the BNS.
2. Mix thoroughly using a glass stirring rod.
3. Divide the BNS/oil mixture equally between two beakers.
4. Divide the NCCF equally into two portions.
5. Add one NCCF portion to Silicone Part A.
6. Add the second NCCF portion to Silicone Part B.
7. Mix each silicone/NCCF mixture thoroughly.
8. Add one silicone mixture to one BNS/oil beaker.
9. Add the second silicone mixture to the remaining BNS/oil beaker.
10. Mix both beakers until homogeneous.
11. Combine both beakers into a single beaker.
12. Stir continuously for 15 minutes.

## 3. Degas Composite

1. Place the composite mixture into a vacuum chamber.
2. Apply vacuum until trapped air bubbles are removed.
3. The chamber gauge typically indicated approximately 25 Pa.
4. Continue degassing for 30 minutes.

> The exact pressure is not critical. The objective is complete removal of visible bubbles.

## 4. Prepare Tubing

1. Cut a 2.5 inch (63.5 mm) section of silicone tubing.
2. Insert a stainless steel rod through the tubing lumen.
3. Ensure the tubing remains straight during molding.

## 5. Mold Conductive Composite Layer

1. Fill the conductive composite bottom mold with the degassed composite.
2. Place the tubing into the mold slots.
3. Fill the conductive composite top mold with composite material.
4. Assemble the mold halves.
5. Secure the mold using trigger clamps.
6. Verify that the tubing remains centered.

### Cure Conditions

- Room temperature cure
- Minimum cure time: 4 hours

## 6. Prepare Outer Silicone Layer

1. Mix equal parts Silicone Part A and Silicone Part B.
2. Stir for approximately 1 minute.
3. Degas in the vacuum chamber for 30 minutes.

During degassing:

1. Remove the cured conductive composite sheath from its mold.
2. Trim excess material using scissors.

## 7. Mold Outer Silicone Encapsulation

1. Fill the silicone bottom mold with the degassed silicone.
2. Place the conductive composite sheath into the mold.
3. Fill the silicone top mold with silicone.
4. Assemble the mold.
5. Secure the mold using trigger clamps.
6. Add additional silicone through the fill holes until completely full.

### Cure Conditions

- Room temperature cure
- Minimum cure time: 6 hours

## 8. Demolding

1. Remove the sensor from the mold.
2. Trim excess silicone.
3. Inspect according to the acceptance criteria below.

---

# Acceptance Criteria

A successfully fabricated sensor should meet the following requirements:

- No visible air bubbles or large voids
- Tubing lumen remains open and unobstructed
- Conductive sheath is continuous around the tubing
- Outer silicone layer fully encapsulates the conductive composite
- Sensor can be removed from the mold without tearing

