# Introduction

## Project Overview

Conductive polymer composites (CPCs) are an emerging class of flexible sensing materials that can change their electrical resistance in response to mechanical deformation. Because CPCs can be fabricated into soft, stretchable structures, they have attracted significant interest for use in wearable electronics, soft robotics, biomedical devices, human motion monitoring, and flexible pressure sensing applications.

Traditional strain gauges are often rigid and are designed to operate over relatively small strain ranges. In contrast, CPC sensors can conform to curved surfaces and undergo much larger deformations while maintaining electrical functionality. These properties make CPCs attractive candidates for future flexible electronic systems.

The long-term goal of this project is to understand how CPC sensor resistance changes in response to mechanical deformation and to develop models that can predict strain using only electrical resistance measurements.

---

# Project Goals

The primary goals of this project are:

1. Measure pressure and sensor resistance simultaneously.
2. Characterize sensor behavior, including drift, hysteresis, and preconditioning effects.
3. Develop relationships between pressure and resistance.
4. Determine the relationship between strain and resistance.
5. Develop predictive models capable of estimating strain from measured resistance.

Ultimately, the objective is to determine whether CPC sensors can be used as reliable strain sensing elements in flexible electronic systems.

---

# Motivation

A significant amount of CPC research has focused on uniaxial strain testing, where a sensor is stretched along a single axis while its electrical response is measured. While these experiments are useful for understanding material behavior, many real-world applications do not experience purely uniaxial deformation.

In biomedical devices, soft robotic actuators, expandable tubing, and other flexible structures, deformation often occurs through radial expansion caused by internal pressure. This type of loading produces circumferential strain rather than simple uniaxial strain.

As a result, it is important to understand how CPC sensors behave when subjected to circumferential strain and whether the behaviors observed during uniaxial testing remain valid under more application-relevant loading conditions.

---

# Circumferential Strain Testing

Rather than stretching the sensor directly, this project generates circumferential strain by pressurizing flexible tubing.

As internal pressure increases, the tubing expands radially. This expansion stretches the CPC sensor and changes its electrical resistance.

The applied pressure is generated using a water manometer. Water is added to or removed from the manometer using a syringe pump, which changes the height of the water column.

The pressure applied to the sensor is determined from the water height and converted into millimeters of mercury (mmHg) using standard hydrostatic pressure relationships.

By controlling the water height, repeatable pressure profiles can be applied to the CPC sensor while its electrical response is measured.

---

# Data Acquisition System

A custom graphical user interface (GUI) was developed to automate data collection and experimental control.

The GUI performs three primary tasks:

1. Measures pressure using an inline pressure transducer.
2. Measures CPC sensor resistance using a Fluke 8808A Digital Multimeter.
3. Controls the syringe pump used to adjust the water level within the manometer.

By integrating these systems into a single interface, pressure and resistance data can be collected simultaneously and synchronized automatically.

---

# Pressure Cycling Experiments

The primary function of the GUI is to automate pressure cycling experiments.

During a test, the system cycles between a user-defined start pressure and end pressure using specified pressure increments. At each pressure level, data is collected for a defined period of time.

Rather than storing individual measurements directly for analysis, the GUI calculates average pressure and average resistance values over the collection period.

These averaged values are then used to generate pressure-resistance plots that characterize sensor behavior.

This averaging process helps reduce measurement noise and provides a more stable representation of the sensor response at each pressure level.

---

# Pressure, Resistance, and Strain Relationships

A major objective of this work is to determine how pressure, strain, and resistance are related.

The current testing platform directly measures:

- Pressure
- Resistance

However, strain is not currently measured.

The working assumption is that increasing pressure causes the tubing to expand, creating strain within the CPC sensor. This strain then alters the conductive pathways within the composite, producing a measurable resistance change.

Future work will focus on directly measuring strain using a camera-based imaging system. By tracking sensor deformation during pressurization, pressure, strain, and resistance data can be collected simultaneously.

This will allow the relationships between:

Pressure → Strain

and

Strain → Resistance

to be quantified independently.

---

# Long-Term Vision

The long-term goal of this project is to create a model capable of predicting sensor strain from electrical resistance measurements alone.

Such a model could allow CPC sensors to function as embedded sensing elements within flexible structures, eliminating the need for external strain measurement systems.

If successful, this approach could contribute to the development of future flexible electronic technologies, including wearable devices, biomedical monitoring systems, soft robotic actuators, and other applications requiring lightweight and compliant sensing solutions.
