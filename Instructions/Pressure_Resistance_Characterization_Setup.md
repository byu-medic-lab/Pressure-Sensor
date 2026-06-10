# Pressure and Resistance Characterization Test Setup

## Overview

This setup is used to characterize the electrical resistance response of a conductive polymer composite (CPC) sensor under controlled hydrostatic pressure conditions. Pressure is determined by the height of a water column within a manometer and is monitored using an inline pressure transducer connected to an Arduino Nano and SparkFun Qwiic Scale board. Sensor resistance is measured simultaneously using a Fluke 8808A Digital Multimeter configured for four-wire resistance measurements.

The water level within the manometer is adjusted using a syringe pump, allowing automated and repeatable pressure profiles. Pressure and resistance measurements are collected and synchronized through a custom graphical user interface (GUI).

The setup consists of the following subsystems:

1. Structural Base Assembly
2. CPC Sensor Assembly
3. Water Manometer
4. Pressure Measurement System
5. Syringe Pump Control System
6. Data Acquisition System

---

# Materials

## Fluidic Components

- Medical-grade tubing (approximately 8.5 ft used for the manometer)
- Medical-grade tubing with male-to-female luer fittings
- 2 × Female Luer Lock to Barb adapters
- 1 × Male-to-Male Luer adapter
- 2 × Three-way stopcocks
- Inline pressure sensor (flow-through pressure transducer)
- Water

## Sensor Components

- Conductive Polymer Composite (CPC) sensor
- Copper tape
- 4 × Alligator clip test leads

## Electronics

- Arduino Nano (ATmega328P)
- Breadboard
- SparkFun Qwiic Scale (NAU7802)
- Qwiic cable (JST-SH 4-pin)
- Micro-USB cable

## Instrumentation

- Fluke 8808A Digital Multimeter
- New Era Pump Systems NE-510L Syringe Pump
- Syringe (diameter not critical)

## Computer Interface Components

- Sabrent HB-UM43 USB Hub
- RJ45 modular communication cable
- DB9 female-to-female null modem adapter
- USB-to-Serial adapter (DB9 female)

## Mechanical Components

- Custom 3D printed base
- Strong adhesive
- Hot glue

---

# System Overview

The system consists of a water-filled manometer connected to a CPC sensor and an inline pressure transducer. Water is added to or removed from the manometer using a syringe pump, changing the height of the water column and therefore the pressure applied to the sensor.

The pressure transducer continuously measures system pressure and transmits the data to an Arduino Nano through a SparkFun Qwiic Scale board. Simultaneously, the Fluke 8808A records the resistance of the CPC sensor using a four-wire measurement configuration.

Pressure and resistance data are collected and synchronized through the data acquisition software.

---

# Mechanical Assembly

## 3D Printed Base

No STL files are currently available for the base.

A suitable replacement can be fabricated using the following approximate dimensions:

- Base length: 20 cm
- Base width: 3 cm
- Platform height: 3 cm
- First platform inward extension: 3 cm
- Second platform inward extension: 4.5 cm

Secure the base to a rigid work surface using strong adhesive to prevent movement during testing.

The base supports:

- One inline pressure transducer
- Two three-way stopcocks

Mount the pressure transducer to one end of the base using hot glue.

Mount both stopcocks using hot glue such that:

- The valve handles remain accessible
- The fluid path is visible
- The CPC sensor can be installed between them

Reference: `3D_Setup`

---

# CPC Sensor Fabrication

The CPC sensor used in this setup is fabricated separately from the testing apparatus.

Fabrication instructions, material recipes, mold construction procedures, curing procedures, and electrical connection methods are provided in a separate document within this repository.

Before beginning testing:

1. Verify that the sensor tubing is free of leaks.
2. Verify that both conductive flaps are electrically continuous.
3. Verify that the luer fittings are securely attached.
4. Inspect the sensor for visible defects or damage.

Reference: `CPC_Sensor_Fabrication`

---

# CPC Sensor Assembly

## Preparing the Sensor

1. Insert a Female Luer Lock to Barb adapter into each end of the CPC sensor tubing.
2. Ensure the tubing is fully seated on both barb fittings.
3. Apply folded pieces of copper tape to the conductive flaps extending from the sensor.

## Four-Wire Resistance Connections

Attach four alligator clips to the copper tape.

### Positive Side

- Current Positive (I+)
- Voltage Positive (V+)

### Negative Side

- Current Negative (I−)
- Voltage Negative (V−)

This creates a four-wire Kelvin resistance measurement configuration.

## Installing the Sensor

Install the CPC sensor between the two stopcocks mounted on the base.

Connect:

- One female luer fitting to the upstream stopcock
- One female luer fitting to the downstream stopcock

Reference: `Sensor_Testing`

---

# Water Manometer Assembly

## Purpose

The manometer provides a known hydrostatic pressure reference for sensor characterization and pressure sensor calibration.

## Construction

1. Suspend approximately 8.5 ft of medical-grade tubing vertically.
2. Secure the tubing to a ceiling, wall, or other rigid structure.
3. Ensure the tubing hangs as vertically as possible.
4. Fill the tubing with water.

The tubing diameter is not critical because pressure is determined by water column height rather than tubing diameter.

## Connections

1. Attach a Male-to-Male Luer adapter to the end of the manometer tubing.
2. Connect the adapter to a three-way stopcock.
3. Connect the stopcock to the pressure transducer assembly.

Reference: `Manometer`

---

# Pressure Calculation

The pressure applied to the sensor is determined by the height of the water column.

Pressure can be calculated using:

Pressure (mmHg) = Height (cm H₂O) × 0.7356

where:

- Height is measured in centimeters of water (cm H₂O)
- Pressure is reported in millimeters of mercury (mmHg)

## Example Values

| Water Height (cm H₂O) | Pressure (mmHg) |
|-----------------------|-----------------|
| 10 | 7.36 |
| 20 | 14.71 |
| 30 | 22.07 |
| 40 | 29.42 |
| 50 | 36.78 |

The pressure transducer is calibrated against these known pressure values to determine the conversion between raw sensor readings and mmHg.

---

# Pressure Measurement System

## Hardware

- Arduino Nano (ATmega328P)
- SparkFun Qwiic Scale (NAU7802)
- Inline pressure transducer
- Breadboard
- Qwiic cable
- Micro-USB cable

## Breadboard Assembly

Mount the Arduino Nano and SparkFun Qwiic Scale on a solderless breadboard.

Connect the pressure transducer wiring to the SparkFun Qwiic Scale according to the board labeling.

The Arduino Nano communicates with the SparkFun Qwiic Scale and transmits pressure measurements to the data acquisition software.

Reference Images:

- `Pressure_Sensor_Breadboard_1`
- `Pressure_Sensor_Breadboard_2`
- `Pressure_Sensor_Breadboard_3`

---

# Syringe Pump Assembly

## Hardware

- New Era Pump Systems NE-510L Syringe Pump
- Syringe
- Medical-grade tubing

## Fluid Connections

1. Install the syringe into the syringe pump and secure it using the pump clamp.
2. Connect tubing to the syringe luer fitting.
3. Connect the opposite end of the tubing to the stopcock mounted on the base.
4. Verify that all fluidic connections are secure and that the system forms a continuous path between the syringe, manometer, pressure transducer, and CPC sensor.

Reference: `Syringe_Pump`

---

# Digital Multimeter Setup

## Hardware

- Fluke 8808A Digital Multimeter
- Four alligator clip leads

## Configuration

1. Connect all four alligator clips to the CPC sensor.
2. Connect the Fluke 8808A to the computer.
3. Select resistance measurement mode.
4. Press the resistance button twice to enable four-wire resistance measurements.

This configuration allows accurate resistance measurements while minimizing lead resistance effects.

Reference: `Fluke_Digital_Multimeter`

---

# Computer Connections

### Connection Summary

| Device | Connection Path |
|----------|----------|
| Arduino Nano | Micro-USB → USB Hub → Computer |
| Pressure Transducer | SparkFun Qwiic Scale → Arduino Nano |
| Syringe Pump | RJ45 Cable → Null Modem Adapter → USB-to-Serial Adapter → USB Hub → Computer |
| Fluke 8808A | USB-to-Serial Adapter → USB Hub → Computer |

---

# Data Collection Procedure

## GUI Setup

1. Connect the Arduino Nano, Fluke 8808A, and syringe pump to the computer through the USB hub.
2. Launch the data acquisition GUI.
3. Select the Arduino COM port.
4. Select the Fluke COM port.
5. Select the syringe pump COM port.
6. Verify communication with all connected devices.

## Pressure Sensor Calibration

1. Fill the fluidic system with water and remove visible air bubbles.
2. Set the manometer to a known water height.
3. Record the corresponding raw pressure sensor reading.
4. Repeat for multiple water heights.
5. Use the collected data to determine the pressure sensor conversion equation.

## Experimental Data Collection

1. Adjust the water level to the desired pressure.
2. Allow the system to stabilize.
3. Begin data collection.
4. Record pressure data from the pressure transducer.
5. Record resistance data from the Fluke 8808A.
6. Continue data collection for the desired duration.
7. Save all generated data files for later analysis.

The GUI synchronizes pressure measurements and resistance measurements for subsequent analysis.

---

# Notes

- The pressure transducer model is currently unknown.
- Ensure all luer connections are tightened before testing.
- Remove as many air bubbles as possible before collecting data.
- Verify stopcock positions before changing pressure.
- The tubing diameter used for the manometer is not critical because pressure is determined by water column height.
- Inspect CPC sensors for leaks or damaged conductive flaps before installation.
