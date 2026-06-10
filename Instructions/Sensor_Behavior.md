# Sensor Behavior

## Overview

This document summarizes the behavior observed in conductive polymer composite (CPC) sensors tested using the pressure characterization setup. The observations described here are based on experimental data collected to date and should be considered preliminary. As additional testing is performed, the explanations and hypotheses presented in this document may be revised.

---

# Key Observations

Several consistent behaviors have been observed across multiple sensors and testing protocols:

1. Electrical drift
2. Hysteresis
3. Cycle-to-cycle resistance changes
4. Preconditioning effects
5. Non-monotonic behavior under certain conditions

These phenomena have been reported in the CPC literature and are common challenges when using conductive polymer composites as strain sensors.

---

# Electrical Drift

The most consistent observation throughout testing has been electrical drift.

When sensors are subjected to repeated pressure cycles, the baseline resistance often changes over time. In many experiments, the resistance measured at the end of a pressure cycle is greater than the resistance measured at the beginning of the cycle, even when the pressure has returned to the same value.

This behavior causes the resistance-pressure relationship to shift over time and complicates direct pressure estimation using resistance alone.

Several potential mechanisms have been proposed in the literature, including:

- Viscoelastic relaxation of the polymer matrix
- Rearrangement of conductive pathways
- Progressive depercolation of the conductive network
- Time-dependent tunneling distance changes between conductive fillers

At present, the exact cause of the observed drift in these sensors remains unknown.

---

# Hysteresis

All sensors tested to date exhibit hysteresis.

For a given pressure, the measured resistance depends on whether the pressure is increasing or decreasing. As a result, loading and unloading curves do not overlap.

The hysteresis magnitude varies between sensors and testing protocols but is consistently present.

This behavior is expected in conductive polymer composites due to:

- Polymer viscoelasticity
- Delayed mechanical recovery
- Time-dependent restructuring of conductive pathways

The presence of hysteresis limits the ability to uniquely determine pressure from resistance without additional compensation methods.

---

# Cycle-to-Cycle Resistance Changes

Repeated pressure cycling frequently produces a gradual increase in resistance between cycles.

In many experiments:

- The first cycle produces the largest response.
- Subsequent cycles produce different resistance-pressure relationships.
- Baseline resistance often increases with continued cycling.

This behavior suggests that the conductive network is changing during repeated loading.

The effect is particularly noticeable during large pressure excursions and long-duration experiments.

---

# Preconditioning Effects

Several experiments have shown evidence of sensor preconditioning.

Preconditioning refers to changes in sensor behavior caused by previous loading history.

Examples observed during testing include:

- Reduced drift after repeated cycling within a specific pressure range.
- Improved repeatability after several initial cycles.
- Different responses after overnight rest periods.
- Changes in behavior following exposure to higher pressures.

In some cases, sensors that initially showed strong resistance increases with pressure later exhibited reduced sensitivity or even reversed trends after repeated loading.

These observations suggest that the conductive network evolves as the sensor experiences mechanical strain.

Identifying stable operating regions through preconditioning may be necessary before reliable measurements can be obtained.

---

# Depercolation Strain

One of the major unanswered questions is the strain level at which depercolation occurs.

Depercolation refers to the breakdown of conductive pathways within the composite as strain increases.

Many CPC sensors exhibit a transition between:

- A relatively stable conductive state
- A highly strain-sensitive depercolation region

At present, the strain experienced by the sensor is not directly measured during testing.

Because strain data is unavailable, it is currently impossible to determine:

- The strain at which depercolation begins
- Whether the sensor is operating below, near, or above the depercolation threshold
- How pressure relates to actual sensor strain

Future work should include direct strain measurements.

A recommended approach is to implement a camera-based measurement system capable of tracking changes in sensor geometry during pressurization. Image-based strain measurements would allow pressure, strain, and resistance data to be analyzed simultaneously.

---

# Comparison to Published Literature

All research papers reviewed to date are stored in Zotero under the folder:

- Strain Gauge and Electrodes

Researchers have reported several behaviors that closely resemble the observations made in this project.

Commonly reported CPC phenomena include:

- Electrical drift
- Hysteresis
- Viscoelastic relaxation
- Resistance baseline shifts
- Preconditioning effects
- Nonlinear sensitivity
- Depercolation-driven behavior

Many publications describe conductive networks that continue to evolve during repeated loading cycles. This often produces changing resistance responses even when identical mechanical loading conditions are applied.

Several studies also report that the first few loading cycles differ substantially from later cycles, suggesting that conductive pathways rearrange as the material is mechanically conditioned.

These observations are generally consistent with the behavior observed in the sensors tested in this project.

---

# Notable Differences from Literature

Although many of the observed behaviors match published results, several questions remain unresolved.

In particular:

- The exact strain experienced by the sensor is unknown.
- The location of the depercolation threshold has not been identified.
- The source of long-term drift remains unclear.
- The relationship between pressure, strain, and resistance has not yet been fully characterized.

Additional experiments combining pressure measurements, resistance measurements, and direct strain measurements will be required to determine whether the observed behavior is consistent with published depercolation models.

---

# Future Work

Recommended future investigations include:

1. Implement camera-based strain measurements.
2. Determine the strain corresponding to various pressure levels.
3. Identify the onset of depercolation.
4. Quantify preconditioning effects.
5. Investigate the effects of overnight rest periods.
6. Compare sensors fabricated with different filler concentrations.
7. Develop models capable of compensating for drift and hysteresis.
8. Evaluate whether stable operating regions exist for long-term sensing applications.

As additional data is collected, this document should be updated to reflect new observations and conclusions.
